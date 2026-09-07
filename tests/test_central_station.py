"""Tests for the shared Central-side station machinery.

These cover the logic that used to exist twice, once per Central. They live here
because this is the repository whose tests run without a database — which is the
same property that let the engine be written dependency-free in the first place.

The sync assertions deliberately mirror ``lazeims-core/tests/test_station_sync.py``
(duplicate replay, payload conflict, one bad event not aborting the batch) so that
moving lazeims-core onto this engine is covered by an executable check rather than
by reading the diff.
"""

from __future__ import annotations

import asyncio
import json
import zipfile
from io import BytesIO

import pytest

from lazeims_common.central import package as central_package
from lazeims_common.central.sync import SyncRejected, process_sync_batch
from lazeims_common.enums import RejectionCode
from lazeims_common.hashing import canonical_bytes, sha256_prefixed
from lazeims_common.schemas.station_package import StationPackageManifest
from lazeims_common.signing import verify_package_signature


def _fake_hash(secret: str) -> str:
    """Stand-in for a Central's Argon2id hasher (not injected here for speed)."""
    return f"$argon2id$fake${secret[::-1]}"


def _seed() -> dict:
    return {
        "schools": [{"centre_number": "s0001", "name": "TEST", "council_name": "C", "region_name": "R"}],
        "subjects": [{"subject_code": "011", "name": "MATH", "papers": ["THEORY1"],
                      "total_marks": {"THEORY1": 100, "THEORY2": 0, "PRACTICAL": 0},
                      "groups": [], "questions": []}],
        "students": [{"student_id": "S0001-0001", "centre_number": "s0001",
                      "first_name": "A", "middle_name": None, "surname": "B", "sex": "F"}],
        "registrations": [{"student_id": "S0001-0001", "subject_code": "011"}],
        "credentials": [],
    }


def _manifest(seed: dict) -> StationPackageManifest:
    config_hash = central_package.compute_configuration_hash(seed)
    return central_package.build_manifest(
        package_id=central_package.compute_package_id(
            station_code="STN-1", package_version=1, configuration_hash=config_hash
        ),
        package_version=1,
        supersedes_package_id=None,
        rules_version="1.0",
        station_code="STN-1",
        exam_id="exam-1",
        exam_name="TEST EXAM",
        configuration_hash=config_hash,
        schools=["s0001"],
        subjects=["011"],
        papers=["THEORY1"],
        central_base_url="https://central.example",
        machine_credential_id="mc_test",
    )


# ── package assembly ─────────────────────────────────────────────────────────

def test_configuration_hash_is_prefixed_and_canonical():
    seed = _seed()
    assert central_package.compute_configuration_hash(seed) == sha256_prefixed(seed)
    assert central_package.compute_configuration_hash(seed).startswith("sha256:")


def test_configuration_hash_ignores_key_order():
    a = {"x": 1, "y": [1, 2]}
    b = {"y": [1, 2], "x": 1}
    assert central_package.compute_configuration_hash(a) == central_package.compute_configuration_hash(b)


def test_package_id_is_content_addressed_and_stable():
    args = dict(station_code="STN-1", package_version=2, configuration_hash="sha256:abc")
    first = central_package.compute_package_id(**args)
    assert first == central_package.compute_package_id(**args)
    assert first.startswith("pkg_")
    assert len(first) == len("pkg_") + 24
    # A different version must not collide.
    assert first != central_package.compute_package_id(
        station_code="STN-1", package_version=3, configuration_hash="sha256:abc"
    )


def test_machine_credential_shape_and_injected_hasher():
    cred = central_package.new_machine_credential(_fake_hash)
    assert cred.credential_id.startswith("mc_")
    assert len(cred.secret) >= 32
    assert cred.secret_hash == _fake_hash(cred.secret)
    # Two credentials never share a secret.
    assert cred.secret != central_package.new_machine_credential(_fake_hash).secret


def test_manifest_declares_the_contract():
    m = _manifest(_seed())
    assert m.contract_version == "station-package/v1"
    assert m.signing.algorithm == "ed25519"
    assert m.machine_credential.algorithm == "argon2id"
    assert m.scope.papers == ["THEORY1"]


def test_bundle_signature_verifies_over_the_serialised_manifest():
    seed = _seed()
    cred = central_package.new_machine_credential(_fake_hash)
    bundle = central_package.assemble_bundle(
        manifest=_manifest(seed), seed=seed, machine_credential=cred,
        station_code="STN-1", central_base_url="https://central.example",
    )
    assert bundle["signature"].startswith("ed25519:")
    assert verify_package_signature(bundle["manifest"], bundle["signature"])
    # The station verifies the dict it parsed out of the ZIP, so signing must
    # cover exactly that dict.
    assert verify_package_signature(
        json.loads(canonical_bytes(bundle["manifest"])), bundle["signature"]
    )


def test_bundle_carries_plaintext_secret_only_in_the_credential_payload():
    seed = _seed()
    cred = central_package.new_machine_credential(_fake_hash)
    bundle = central_package.assemble_bundle(
        manifest=_manifest(seed), seed=seed, machine_credential=cred,
        station_code="STN-1", central_base_url="https://central.example",
    )
    assert bundle["machine_credential"]["secret"] == cred.secret
    assert cred.secret not in json.dumps(bundle["manifest"])


def test_zip_contains_every_contract_file_and_correct_hashes():
    seed = _seed()
    cred = central_package.new_machine_credential(_fake_hash)
    bundle = central_package.assemble_bundle(
        manifest=_manifest(seed), seed=seed, machine_credential=cred,
        station_code="STN-1", central_base_url="https://central.example",
    )
    zf = zipfile.ZipFile(BytesIO(central_package.build_package_zip(bundle)))
    assert set(central_package.PACKAGE_FILES) <= set(zf.namelist())
    assert "SHA256SUMS" in zf.namelist()
    assert "README.txt" in zf.namelist()

    # SHA256SUMS must describe the bytes actually written.
    import hashlib
    listed = {
        line.split("  ")[1]: line.split("  ")[0]
        for line in zf.read("SHA256SUMS").decode().strip().split("\n")
    }
    for name, digest in listed.items():
        assert hashlib.sha256(zf.read(name)).hexdigest() == digest, name


def test_zip_json_is_the_canonical_form_that_was_signed():
    """The bytes on disk are the bytes the signature covers.

    Guards the divergence that existed before this module: each Central had a
    private ``_canonical`` writer, one of which escaped non-ASCII while the
    shared hasher does not.
    """
    seed = _seed()
    seed["schools"][0]["name"] = "MBULU SEKONDARI ÅÄÖ"
    cred = central_package.new_machine_credential(_fake_hash)
    bundle = central_package.assemble_bundle(
        manifest=_manifest(seed), seed=seed, machine_credential=cred,
        station_code="STN-1", central_base_url="https://central.example",
    )
    zf = zipfile.ZipFile(BytesIO(central_package.build_package_zip(bundle)))
    assert zf.read("seed.json") == canonical_bytes(seed)
    assert zf.read("manifest.json") == canonical_bytes(bundle["manifest"])
    # And the station's integrity check still passes on the written bytes.
    assert sha256_prefixed(json.loads(zf.read("seed.json"))) == bundle["manifest"]["configuration_hash"]


def test_zip_readme_names_the_issuing_central():
    seed = _seed()
    cred = central_package.new_machine_credential(_fake_hash)
    bundle = central_package.assemble_bundle(
        manifest=_manifest(seed), seed=seed, machine_credential=cred,
        station_code="STN-1", central_base_url="https://central.example",
    )
    readme = zipfile.ZipFile(
        BytesIO(central_package.build_package_zip(bundle, central_name="ExaMetrics"))
    ).read("README.txt").decode()
    assert "ExaMetrics exam package" in readme
    assert "https://central.example" in readme


# ── sync engine ──────────────────────────────────────────────────────────────

class _Store:
    """Minimal in-memory stand-in for a Central's receipt table + savepoints."""

    def __init__(self):
        self.receipts: dict[str, object] = {}
        self.applied: list[str] = []
        self.rolled_back = 0

    async def get(self, event_id):
        return self.receipts.get(event_id)

    async def put(self, *, event_id, entity_type, status, payload_hash, rejection_code):
        self.receipts[event_id] = type(
            "R", (), {"payload_hash": payload_hash, "status": status,
                      "rejection_code": rejection_code, "entity_type": entity_type}
        )()

    async def savepoint(self):
        store = self

        class _SP:
            async def commit(self):
                pass

            async def rollback(self):
                store.rolled_back += 1

        return _SP()


def _event(event_id, value, entity_type="STUDENT_PAPER_MARKS_REPLACED"):
    return {
        "event_id": event_id,
        "entity_type": entity_type,
        "operation": "UPSERT",
        "natural_key": {"student_id": "S0001-0001", "subject_code": "011", "paper_type": "THEORY1"},
        "value": value,
        "local_version": 1,
        "actor_assignment_id": "1",
        "occurred_at": "2026-01-01T00:00:00+00:00",
    }


def _run(coro):
    return asyncio.run(coro)


def test_accepts_a_batch_and_reports_per_event():
    store = _Store()

    async def apply(event):
        store.applied.append(event["event_id"])

    resp = _run(process_sync_batch(
        [_event("evt_a", {"is_present": True}, "ATTENDANCE_TRANSCRIBED"),
         _event("evt_m", {"mode": "TOTAL_MARKS", "total": "67"})],
        apply_event=apply, get_receipt=store.get, put_receipt=store.put,
        savepoint=store.savepoint,
    ))
    assert {e["event_id"] for e in resp["accepted"]} == {"evt_a", "evt_m"}
    assert resp["rejected"] == []
    assert resp["duplicates"] == []
    assert store.applied == ["evt_a", "evt_m"]
    assert "server_time" in resp


def test_duplicate_replay_returns_duplicate_and_does_not_reapply():
    store = _Store()

    async def apply(event):
        store.applied.append(event["event_id"])

    events = [_event("evt_a", {"mode": "TOTAL_MARKS", "total": "67"})]
    _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                            put_receipt=store.put, savepoint=store.savepoint))
    resp = _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                                   put_receipt=store.put, savepoint=store.savepoint))
    assert resp["duplicates"] == [{"event_id": "evt_a"}]
    assert resp["accepted"] == []
    assert store.applied == ["evt_a"], "the second send must not apply again"


def test_same_event_id_with_different_payload_is_a_conflict():
    store = _Store()

    async def apply(event):
        store.applied.append(event["event_id"])

    _run(process_sync_batch([_event("evt_a", {"mode": "TOTAL_MARKS", "total": "67"})],
                            apply_event=apply, get_receipt=store.get,
                            put_receipt=store.put, savepoint=store.savepoint))
    resp = _run(process_sync_batch([_event("evt_a", {"mode": "TOTAL_MARKS", "total": "99"})],
                                   apply_event=apply, get_receipt=store.get,
                                   put_receipt=store.put, savepoint=store.savepoint))
    assert resp["rejected"][0]["code"] == RejectionCode.EVENT_ID_PAYLOAD_CONFLICT.value
    assert store.applied == ["evt_a"], "a conflicting replay must not overwrite"


def test_one_bad_event_does_not_abort_the_batch():
    store = _Store()

    async def apply(event):
        if event["event_id"] == "evt_bad":
            raise SyncRejected(RejectionCode.MARK_OUT_OF_RANGE, "too big")
        store.applied.append(event["event_id"])

    resp = _run(process_sync_batch(
        [_event("evt_a", {"is_present": True}, "ATTENDANCE_TRANSCRIBED"),
         _event("evt_bad", {"mode": "TOTAL_MARKS", "total": "9999"}),
         _event("evt_c", {"mode": "TOTAL_MARKS", "total": "50"})],
        apply_event=apply, get_receipt=store.get, put_receipt=store.put,
        savepoint=store.savepoint,
    ))
    assert {e["event_id"] for e in resp["accepted"]} == {"evt_a", "evt_c"}
    assert resp["rejected"][0]["event_id"] == "evt_bad"
    assert resp["rejected"][0]["code"] == "MARK_OUT_OF_RANGE"
    assert store.rolled_back == 1


def test_rejection_receipt_survives_the_savepoint_rollback():
    """A rejected event must be remembered, or the station retries it forever."""
    store = _Store()

    async def apply(event):
        raise SyncRejected(RejectionCode.NOT_REGISTERED, "unknown student")

    _run(process_sync_batch([_event("evt_x", {"mode": "TOTAL_MARKS", "total": "1"})],
                            apply_event=apply, get_receipt=store.get,
                            put_receipt=store.put, savepoint=store.savepoint))
    assert "evt_x" in store.receipts
    assert store.receipts["evt_x"].status == "REJECTED"
    assert store.receipts["evt_x"].rejection_code == "NOT_REGISTERED"


def test_gate_refuses_before_apply_but_after_dedupe():
    store = _Store()

    async def apply(event):
        store.applied.append(event["event_id"])

    async def gate(event):
        return ("RESULTS_PUBLISHED", "results are published")

    events = [_event("evt_a", {"mode": "TOTAL_MARKS", "total": "67"})]
    resp = _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                                   put_receipt=store.put, savepoint=store.savepoint, gate=gate))
    assert resp["rejected"][0]["code"] == "RESULTS_PUBLISHED"
    assert store.applied == []

    # Already-recorded events are still deduped while the gate is closed, so a
    # station replaying a batch is not told to retry work that already landed.
    store.receipts.clear()
    _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                            put_receipt=store.put, savepoint=store.savepoint))
    resp2 = _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                                    put_receipt=store.put, savepoint=store.savepoint, gate=gate))
    assert resp2["duplicates"] == [{"event_id": "evt_a"}]
    assert resp2["rejected"] == []


def test_gate_refusal_writes_no_receipt_so_a_retry_can_still_land():
    """A temporary refusal must not become a permanent silent loss.

    A gate says "not now" (the exam is published, the phase is locked). If that
    were recorded as a receipt, the station's next attempt at the same event_id
    would come back ``duplicate``, the station would mark it accepted, and the
    marks would never be sent again. A rejection from ``apply_event`` is
    different in kind — a mark over the maximum will not become valid — and does
    get a receipt.
    """
    store = _Store()
    gate_state = {"closed": True}

    async def apply(event):
        store.applied.append(event["event_id"])

    async def gate(event):
        return ("RESULTS_PUBLISHED", "results are published") if gate_state["closed"] else None

    events = [_event("evt_a", {"mode": "TOTAL_MARKS", "total": "67"})]
    _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                            put_receipt=store.put, savepoint=store.savepoint, gate=gate))
    assert store.receipts == {}, "a gate refusal must leave no receipt"
    assert store.applied == []

    # Seal lifted: the very same event_id must now be applied, not deduped away.
    gate_state["closed"] = False
    resp = _run(process_sync_batch(events, apply_event=apply, get_receipt=store.get,
                                   put_receipt=store.put, savepoint=store.savepoint, gate=gate))
    assert [e["event_id"] for e in resp["accepted"]] == ["evt_a"]
    assert store.applied == ["evt_a"]


def test_unexpected_errors_are_not_swallowed_as_rejections():
    """Only SyncRejected is a business rejection; a bug must surface."""
    store = _Store()

    async def apply(event):
        raise KeyError("natural_key")

    with pytest.raises(KeyError):
        _run(process_sync_batch([_event("evt_a", {})], apply_event=apply,
                                get_receipt=store.get, put_receipt=store.put,
                                savepoint=store.savepoint))
