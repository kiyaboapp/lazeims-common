"""Tests for the §12 shared contract fixtures.

Every fixture is validated against the schema it claims to match, so a shape
that drifts fails here first — in the repo that owns the contract — rather than
in one of the three consumers. The digest assertion is the load-bearing one:
backend-sis and Central both assert ``frozen_digest()`` against their own
computation, so if this file passes and one of theirs fails, the disagreement is
real data, not two implementations of canonicalisation.
"""

from __future__ import annotations

import copy

from lazeims_common.exametrics_digest import (
    chunk_manifest,
    chunk_payload,
    collection_digest,
    merge_chunks,
)
from lazeims_common.fixtures import exametrics as fx
from lazeims_common.schemas.exametrics import (
    CONTRACT_VERSION,
    CapabilitiesResponse,
    EntitlementsResponse,
    ErrorEnvelope,
    ExamProvisionRequest,
    ExamProvisionResponse,
    ProcessingQuoteOut,
    ProcessingRequestIn,
    ProcessingRequestOut,
    RowValidationDetail,
    WebhookEnvelope,
)


# ─── Each fixture validates against its schema ───────────────────────────────────

def test_identity_response_validates_as_capabilities_response():
    resp = CapabilitiesResponse.model_validate(fx.IDENTITY_RESPONSE)
    assert resp.contract_version == CONTRACT_VERSION
    assert resp.tenant_exam.id == fx.EXAM_REF
    assert resp.capabilities["collection.push"] is True
    assert resp.capabilities["processing.execute"] is False


def test_identity_response_carries_the_deprecated_tenant_mirror():
    """This is the payload D7 exists for: both keys, byte-identical."""
    assert fx.IDENTITY_RESPONSE["tenant"] == fx.IDENTITY_RESPONSE["tenant_exam"]


def test_identity_response_never_carries_the_secret():
    assert "api_key" not in fx.IDENTITY_RESPONSE
    assert fx.IDENTITY_RESPONSE["key_prefix"]


def test_exam_provision_request_validates():
    req = ExamProvisionRequest.model_validate(fx.EXAM_PROVISION_REQUEST)
    assert req.external_ref == fx.EXTERNAL_REF
    assert [s.subject_code for s in req.subjects] == ["011", "032"]
    assert req.subjects[1].theory_2_max == 30.0
    assert req.subjects[1].has_practical is True


def test_exam_provision_response_validates_with_a_structured_warning():
    resp = ExamProvisionResponse.model_validate(fx.EXAM_PROVISION_RESPONSE)
    assert resp.warnings[0].code == "SUBJECT_MAX_MARKS_DIFFERS"
    assert resp.warnings[0].subject_code == "011"


def test_entitlements_fixtures_validate():
    approved = EntitlementsResponse.model_validate(fx.ENTITLEMENTS_APPROVED)
    assert approved.processing.state == "APPROVED"
    assert approved.processing.valid_for_configuration_hash == fx.CONFIGURATION_HASH
    assert approved.results.reason == "PROCESSING_NOT_COMPLETE"

    locked = EntitlementsResponse.model_validate(fx.ENTITLEMENTS_LOCKED)
    assert locked.processing.state == "NONE"
    assert locked.results.reason == "SCOPE_NOT_GRANTED"


def test_the_two_entitlement_fixtures_separate_not_yet_from_not_allowed():
    """§13.4: the two locked results states must be distinguishable."""
    assert (
        fx.ENTITLEMENTS_APPROVED["results"]["reason"]
        != fx.ENTITLEMENTS_LOCKED["results"]["reason"]
    )


def test_processing_request_in_validates():
    req = ProcessingRequestIn.model_validate(fx.PROCESSING_REQUEST_IN)
    assert req.closeout_revision == fx.CLOSEOUT_REVISION
    assert req.configuration_hash == fx.CONFIGURATION_HASH
    assert req.counts.students == fx.COLLECTION_COUNTS["students"]
    assert req.requested_by is not None and req.requested_by.name == "A. Mwita"


def test_processing_request_pending_validates_as_the_202_body():
    out = ProcessingQuoteOut.model_validate(fx.PROCESSING_REQUEST_PENDING)
    assert out.state == "PENDING_APPROVAL"
    assert out.approval.method == "EXAMETRICS_CONSOLE"
    assert out.replayed is False


def test_processing_request_approved_validates_as_a_stored_request():
    out = ProcessingRequestOut.model_validate(fx.PROCESSING_REQUEST_APPROVED)
    assert out.state == "APPROVED"
    assert out.run_id
    assert out.decided_by == "billing@exametrics.example"


def test_webhook_completed_validates():
    hook = WebhookEnvelope.model_validate(fx.WEBHOOK_COMPLETED)
    assert hook.event == "processing.completed"
    assert hook.request_id == fx.REQUEST_ID
    assert hook.state == "COMPLETED"


def test_validation_failed_422_validates_row_by_row():
    envelope = ErrorEnvelope.model_validate(fx.VALIDATION_FAILED_422)
    assert envelope.error.code == "VALIDATION_FAILED"
    rows = [RowValidationDetail.model_validate(d) for d in envelope.error.details]
    assert [r.student_id for r in rows] == ["S0201-0001", "S0198-0001"]
    assert rows[0].paper == "THEORY2"


# ─── The digest both repos assert against ────────────────────────────────────────

def test_collection_payload_digest_equals_the_frozen_digest():
    assert collection_digest(fx.COLLECTION_PAYLOAD) == fx.frozen_digest()


def test_frozen_digest_matches_the_module_constant():
    assert fx.frozen_digest() == fx.FROZEN_COLLECTION_DIGEST
    assert fx.digest_of_collection_payload() == fx.FROZEN_COLLECTION_DIGEST


def test_collection_payload_is_stored_in_non_canonical_order():
    """Otherwise the digest assertion would pass for the wrong reason."""
    assert fx.COLLECTION_PAYLOAD != merge_chunks([fx.COLLECTION_PAYLOAD])


def test_collection_payload_carries_explicit_nulls():
    assert any(row["middle_name"] is None for row in fx.COLLECTION_PAYLOAD["students"])
    assert any(row["theory_2_max"] is None for row in fx.COLLECTION_PAYLOAD["subjects"])


def test_chunked_collection_payload_digests_identically():
    chunks = chunk_payload(fx.COLLECTION_PAYLOAD, 2)
    assert chunk_manifest(chunks)["digest"] == fx.frozen_digest()


# ─── Internal coherence, so backend-sis can assert both halves ───────────────────

def test_collection_counts_match_the_collection_payload():
    payload = fx.COLLECTION_PAYLOAD
    assert fx.COLLECTION_COUNTS["students"] == len(payload["students"])
    assert fx.COLLECTION_COUNTS["centres"] == len(payload["schools"])
    assert fx.COLLECTION_COUNTS["subject_registrations"] == len(payload["marks"])


def test_quote_amount_is_the_billable_count_times_the_unit_amount():
    quote = fx.PROCESSING_REQUEST_PENDING["quote"]
    assert quote["amount"] == quote["billable_students"] * quote["unit_amount"]
    assert quote["unit"] == "per_student"
    assert quote["unit_amount"] == fx.UNIT_AMOUNT
    assert quote["billable_students"] == fx.COLLECTION_COUNTS["students"]


def test_approved_request_freezes_the_quote_it_was_approved_with():
    assert (
        fx.PROCESSING_REQUEST_APPROVED["quote"] == fx.PROCESSING_REQUEST_PENDING["quote"]
    )
    assert (
        fx.PROCESSING_REQUEST_APPROVED["billable_count"]
        == fx.PROCESSING_REQUEST_PENDING["quote"]["billable_students"]
    )


def test_every_fixture_refers_to_the_same_exam_and_request():
    assert fx.PROCESSING_REQUEST_IN["external_ref"] == fx.EXTERNAL_REF
    assert fx.PROCESSING_REQUEST_APPROVED["exam_ref"] == fx.EXAM_REF
    assert fx.WEBHOOK_COMPLETED["exam_ref"] == fx.EXAM_REF
    assert fx.ENTITLEMENTS_APPROVED["exam_ref"] == fx.EXAM_REF
    assert fx.EXAM_PROVISION_RESPONSE["exam_ref"] == fx.EXAM_REF


def test_the_approval_bindings_agree_across_fixtures():
    """A revision or hash that differs between fixtures would make §5.2 untestable."""
    revision = fx.CLOSEOUT_REVISION
    hash_ = fx.CONFIGURATION_HASH
    assert fx.PROCESSING_REQUEST_IN["closeout_revision"] == revision
    assert fx.PROCESSING_REQUEST_APPROVED["closeout_revision"] == revision
    assert fx.ENTITLEMENTS_APPROVED["closeout_revision"] == revision
    assert fx.EXAM_PROVISION_REQUEST["configuration_hash"] == hash_
    assert fx.PROCESSING_REQUEST_APPROVED["configuration_hash"] == hash_
    assert (
        fx.ENTITLEMENTS_APPROVED["processing"]["valid_for_configuration_hash"] == hash_
    )


def test_fixtures_are_json_serialisable_as_they_stand():
    """They go on a wire in the consuming tests, so no datetimes or Decimals."""
    import json

    for name in fx.__all__:
        value = getattr(fx, name)
        if isinstance(value, (dict, list, str, int)):
            json.loads(json.dumps(value))


def test_fixtures_are_not_mutated_by_validating_them():
    before = copy.deepcopy(fx.COLLECTION_PAYLOAD)
    collection_digest(fx.COLLECTION_PAYLOAD)
    chunk_payload(fx.COLLECTION_PAYLOAD, 2)
    assert fx.COLLECTION_PAYLOAD == before
