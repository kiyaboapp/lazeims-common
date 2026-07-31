"""Tests for the shared collection digest (K3).

The properties asserted here are the *contract*: if any of them changes, every
digest on both sides of the boundary changes with it, and a digest-verified
chunked upload starts rejecting good data.
"""

from __future__ import annotations

import copy

import pytest

from lazeims_common import (
    canonical_collection,
    chunk_manifest,
    chunk_payload,
    collection_digest,
    merge_chunks,
)
from lazeims_common.exametrics_digest import (
    COLLECTION_NAMES,
    DEFAULT_CHUNK_ROWS,
    canonical_collection_bytes,
    chunk_rows,
)


def _payload() -> dict:
    """A small payload in Central's natural (unsorted) emission order."""
    return {
        "schools": [
            {"centre_number": "S0201", "school_name": "Mwanza", "region_name": "Mwanza"},
            {"centre_number": "S0198", "school_name": "Ilemela", "region_name": "Mwanza"},
        ],
        "subjects": [
            {"subject_code": "032", "subject_name": "PHYSICS", "theory_max": 50.0},
            {"subject_code": "011", "subject_name": "HISTORY", "theory_max": 100.0},
        ],
        "students": [
            {"student_id": "S0201-0002", "centre_number": "S0201", "surname": "Kileo"},
            {"student_id": "S0198-0001", "centre_number": "S0198", "surname": "Shayo"},
            {"student_id": "S0201-0001", "centre_number": "S0201", "surname": "Mwenda"},
        ],
        "marks": [
            {"student_id": "S0201-0001", "centre_number": "S0201", "subject_code": "032",
             "theory_marks": 38.0},
            {"student_id": "S0201-0001", "centre_number": "S0201", "subject_code": "011",
             "theory_marks": 72.0},
            {"student_id": "S0198-0001", "centre_number": "S0198", "subject_code": "011",
             "theory_marks": 41.0},
        ],
    }


# ─── canonical_collection ────────────────────────────────────────────────────────

def test_canonical_collection_sorts_every_collection_by_its_natural_key():
    canonical = canonical_collection(_payload())
    assert [r["centre_number"] for r in canonical["schools"]] == ["S0198", "S0201"]
    assert [r["subject_code"] for r in canonical["subjects"]] == ["011", "032"]
    assert [r["student_id"] for r in canonical["students"]] == [
        "S0198-0001", "S0201-0001", "S0201-0002",
    ]
    assert [(r["student_id"], r["subject_code"]) for r in canonical["marks"]] == [
        ("S0198-0001", "011"), ("S0201-0001", "011"), ("S0201-0001", "032"),
    ]


def test_canonical_collection_drops_null_values():
    payload = _payload()
    payload["students"][0]["middle_name"] = None
    canonical = canonical_collection(payload)
    assert all("middle_name" not in row for row in canonical["students"])


def test_canonical_collection_does_not_mutate_its_input():
    payload = _payload()
    before = copy.deepcopy(payload)
    canonical_collection(payload)
    assert payload == before


def test_canonical_collection_omits_collections_absent_from_the_payload():
    canonical = canonical_collection({"schools": []})
    assert list(canonical) == ["schools"]


def test_canonical_collection_carries_through_envelope_keys():
    """A non-collection top-level key is still part of what gets digested."""
    canonical = canonical_collection({"schools": [], "closeout_revision": 2})
    assert canonical["closeout_revision"] == 2


def test_collection_names_matches_the_documented_collections():
    assert COLLECTION_NAMES == ("schools", "subjects", "students", "marks")


# ─── collection_digest ───────────────────────────────────────────────────────────

def test_digest_is_prefixed_sha256():
    digest = collection_digest(_payload())
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_shuffling_rows_and_adding_explicit_nulls_leaves_the_digest_unchanged():
    """The whole point of K3: two sides holding the same data agree on the digest."""
    baseline = collection_digest(_payload())

    shuffled = _payload()
    for name in COLLECTION_NAMES:
        shuffled[name] = list(reversed(shuffled[name]))
    for row in shuffled["students"]:
        row["middle_name"] = None
    for row in shuffled["marks"]:
        row["practical_marks"] = None

    assert collection_digest(shuffled) == baseline


def test_reordering_keys_within_a_row_leaves_the_digest_unchanged():
    reordered = _payload()
    reordered["schools"] = [
        {k: row[k] for k in reversed(list(row))} for row in reordered["schools"]
    ]
    assert collection_digest(reordered) == collection_digest(_payload())


def test_changing_a_mark_changes_the_digest():
    changed = _payload()
    changed["marks"][0]["theory_marks"] = 39.0
    assert collection_digest(changed) != collection_digest(_payload())


def test_an_explicit_zero_is_not_dropped_like_a_null():
    """0 and False are data; only None is absence."""
    with_zero = _payload()
    with_zero["marks"][0]["theory_marks"] = 0
    without = _payload()
    without["marks"][0].pop("theory_marks")
    assert collection_digest(with_zero) != collection_digest(without)


def test_a_false_flag_is_not_dropped_like_a_null():
    with_false = _payload()
    with_false["marks"][0]["sat_theory"] = False
    with_null = _payload()
    with_null["marks"][0]["sat_theory"] = None
    assert collection_digest(with_false) != collection_digest(with_null)


def test_empty_collections_digest_differently_from_absent_ones():
    assert collection_digest({"schools": []}) != collection_digest({})


def test_canonical_bytes_are_what_the_digest_covers():
    import hashlib

    payload = _payload()
    expected = hashlib.sha256(canonical_collection_bytes(payload)).hexdigest()
    assert collection_digest(payload) == f"sha256:{expected}"


# ─── chunk_payload / merge_chunks ────────────────────────────────────────────────

def test_chunks_reassemble_to_the_same_digest_as_the_whole():
    payload = _payload()
    for max_rows in (1, 2, 3, 5, 11, 1000):
        chunks = chunk_payload(payload, max_rows)
        assert collection_digest(merge_chunks(chunks)) == collection_digest(payload)


def test_no_chunk_exceeds_max_rows():
    chunks = chunk_payload(_payload(), 4)
    assert all(chunk_rows(chunk) <= 4 for chunk in chunks)
    assert sum(chunk_rows(chunk) for chunk in chunks) == 10


def test_chunks_draw_rows_in_dependency_order():
    """Schools and subjects land before the students and marks referencing them."""
    chunks = chunk_payload(_payload(), 2)
    seen: list[str] = []
    for chunk in chunks:
        for name in COLLECTION_NAMES:
            if chunk[name]:
                seen.append(name)
    assert seen == sorted(seen, key=COLLECTION_NAMES.index)


def test_every_chunk_carries_every_collection_key():
    for chunk in chunk_payload(_payload(), 2):
        assert set(chunk) == set(COLLECTION_NAMES)


def test_an_empty_payload_still_yields_one_chunk():
    chunks = chunk_payload({"schools": [], "subjects": [], "students": [], "marks": []})
    assert len(chunks) == 1
    assert chunk_rows(chunks[0]) == 0


def test_chunk_payload_rejects_a_non_positive_max_rows():
    with pytest.raises(ValueError):
        chunk_payload(_payload(), 0)


def test_default_chunk_rows_matches_the_published_limit():
    assert DEFAULT_CHUNK_ROWS == 5000


# ─── chunk_manifest ──────────────────────────────────────────────────────────────

def test_manifest_reports_the_whole_payload_digest():
    payload = _payload()
    manifest = chunk_manifest(chunk_payload(payload, 3))
    assert manifest["digest"] == collection_digest(payload)
    assert manifest["chunk_count"] == 4
    assert manifest["total_rows"] == 10


def test_manifest_addresses_each_chunk_individually():
    manifest = chunk_manifest(chunk_payload(_payload(), 3))
    assert [c["index"] for c in manifest["chunks"]] == [0, 1, 2, 3]
    assert [c["rows"] for c in manifest["chunks"]] == [3, 3, 3, 1]
    assert all(c["digest"].startswith("sha256:") for c in manifest["chunks"])


def test_manifest_chunk_digests_differ_when_a_chunk_differs():
    chunks = chunk_payload(_payload(), 3)
    tampered = copy.deepcopy(chunks)
    tampered[0]["schools"][0]["school_name"] = "Somewhere else"
    before = chunk_manifest(chunks)
    after = chunk_manifest(tampered)
    assert before["chunks"][0]["digest"] != after["chunks"][0]["digest"]
    assert before["chunks"][1]["digest"] == after["chunks"][1]["digest"]
    assert before["digest"] != after["digest"]
