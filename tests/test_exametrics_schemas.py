"""Tests for the ExaMetrics integration contract schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from lazeims_common import EXAMETRICS_INTEGRATION_CONTRACT
from lazeims_common.schemas.exametrics import (
    CONTRACT_VERSION,
    ApprovalInstruction,
    CapabilitiesResponse,
    CollectionChunkAck,
    CollectionCounts,
    CollectionSessionComplete,
    CollectionSessionStart,
    EntitlementsResponse,
    EntitlementState,
    ErrorBody,
    ErrorEnvelope,
    ExamProvisionRequest,
    ExamProvisionResponse,
    KeyProvisionRequest,
    KeyProvisionResponse,
    ProcessingQuoteOut,
    ProcessingRequestIn,
    ProcessingRequestOut,
    ProvisionWarning,
    QuoteOut,
    RequesterInfo,
    RowValidationDetail,
    SubjectSpec,
    TenantExamInfo,
    TenantInfo,
    WebhookEnvelope,
)


# ─── Contract constant ───────────────────────────────────────────────────────────

def test_exametrics_integration_contract_importable():
    assert EXAMETRICS_INTEGRATION_CONTRACT == "exametrics-integration/v2"


def test_contract_version_matches_constant():
    assert CONTRACT_VERSION == EXAMETRICS_INTEGRATION_CONTRACT


# ─── ExamProvisionRequest ────────────────────────────────────────────────────────

def test_provision_request_minimal():
    req = ExamProvisionRequest(
        external_ref="CSEE-2026-ZONE1",
        name="CSEE 2026",
        level="CSEE",
    )
    assert req.external_ref == "CSEE-2026-ZONE1"
    assert req.level == "CSEE"
    assert req.rules_version == "1.0"
    assert req.subjects == []


def test_provision_request_full():
    req = ExamProvisionRequest(
        external_ref="FTNA-2026-Z2",
        name="FTNA 2026 Zone 2",
        exam_code="FTNA-2026",
        level="FTNA",
        board="board-001",
        start_date="2026-06-01",
        end_date="2026-06-30",
        zone_name="Zone 2",
        filling_mode="ITEM_LEVEL",
        rules_version="1.0",
        configuration_hash="sha256:abc123",
        subjects=[
            {"subject_code": "011", "subject_name": "CIVICS"},
            {"subject_code": "021", "subject_name": "HISTORY", "has_practical": False, "has_theory_2": True},
        ],
    )
    assert len(req.subjects) == 2
    assert req.subjects[1].has_theory_2 is True


def test_provision_request_external_ref_required():
    with pytest.raises(PydanticValidationError):
        ExamProvisionRequest(name="Test", level="CSEE")


def test_provision_request_empty_external_ref_rejected():
    with pytest.raises(PydanticValidationError):
        ExamProvisionRequest(external_ref="", name="Test", level="CSEE")


def test_provision_request_forbids_extra_fields():
    with pytest.raises(PydanticValidationError):
        ExamProvisionRequest(
            external_ref="X",
            name="Test",
            level="CSEE",
            unexpected_field="oops",
        )


# ─── ExamProvisionResponse ───────────────────────────────────────────────────────

def test_provision_response_minimal():
    resp = ExamProvisionResponse(
        exam_ref="exam-uuid-123",
        external_ref="CSEE-2026-Z1",
        state="CREATED",
        created=True,
    )
    assert resp.configuration_accepted is True
    assert resp.warnings == []


def test_provision_response_with_warnings():
    resp = ExamProvisionResponse(
        exam_ref="exam-uuid-123",
        external_ref="CSEE-2026-Z1",
        state="UPDATED",
        created=False,
        configuration_accepted=False,
        warnings=[
            {"code": "CONFIGURATION_HASH_MISMATCH", "message": "Configuration hash mismatch"},
            {
                "code": "SUBJECT_MAX_MARKS_DIFFERS",
                "message": "Existing definition had theory_max 90; updated to 100.",
                "subject_code": "011",
                "field": "theory_max",
            },
        ],
    )
    assert len(resp.warnings) == 2
    assert resp.warnings[1].subject_code == "011"
    assert resp.configuration_accepted is False


def test_provision_warnings_are_structured_not_strings():
    """A bare string cannot address the offending subject, so it is rejected."""
    with pytest.raises(PydanticValidationError):
        ExamProvisionResponse(
            exam_ref="exam-uuid-123",
            external_ref="CSEE-2026-Z1",
            state="UPDATED",
            created=False,
            warnings=["Configuration hash mismatch"],
        )


def test_provision_warning_minimal():
    w = ProvisionWarning(code="SUBJECT_MAX_MARKS_DIFFERS", message="theory_max changed")
    assert w.subject_code is None
    assert w.field is None


# ─── CapabilitiesResponse ────────────────────────────────────────────────────────

def test_capabilities_response_full():
    resp = CapabilitiesResponse(
        tenant=TenantInfo(id="exam-001", name="CSEE 2026", environment="production"),
        capabilities={
            "exam.provision": True,
            "collection.push": True,
            "registrations.extract": True,
            "exam.read": True,
            "processing.request": True,
            "processing.execute": False,
            "results.read": False,
            "results.download": False,
        },
        limits={"max_collection_chunk_size": 5000},
        supported_rules_versions=["1.0"],
    )
    assert resp.contract_version == "exametrics-integration/v2"
    assert resp.capabilities["collection.push"] is True
    assert resp.capabilities["processing.execute"] is False


def test_capabilities_response_defaults():
    resp = CapabilitiesResponse(
        tenant=TenantInfo(id="exam-001"),
        capabilities={"exam.provision": True},
    )
    assert resp.contract_version == CONTRACT_VERSION
    assert resp.limits == {}
    assert resp.supported_rules_versions == ["1.0"]


def test_capabilities_response_tenant_defaults():
    t = TenantInfo(id="exam-001")
    assert t.name is None
    assert t.environment == "production"


def test_tenant_info_is_deprecated_alias_of_tenant_exam_info():
    assert TenantInfo is TenantExamInfo


def test_capabilities_accepts_tenant_exam_key():
    resp = CapabilitiesResponse(
        tenant_exam={"id": "exam-001", "name": "CSEE 2026"},
        capabilities={"collection.push": True},
    )
    assert resp.tenant_exam.id == "exam-001"


def test_capabilities_accepts_legacy_tenant_key():
    resp = CapabilitiesResponse(
        tenant={"id": "exam-001", "name": "CSEE 2026"},
        capabilities={"collection.push": True},
    )
    assert resp.tenant_exam.name == "CSEE 2026"


def test_capabilities_dump_emits_tenant_exam_only():
    resp = CapabilitiesResponse(
        tenant={"id": "exam-001"},
        capabilities={"collection.push": True},
    )
    dumped = resp.model_dump(by_alias=True)
    assert "tenant_exam" in dumped
    assert "tenant" not in dumped


# ─── D7: the payload backend-sis really emits ─────────────────────────────────────

def test_capabilities_accepts_both_tenant_keys_at_once():
    """backend-sis's identity_payload() emits tenant_exam AND the tenant mirror.

    Under ``extra="forbid"`` the mirror is an unexpected extra — the alias only
    ever fills one field — so validating the genuine payload raised
    ``extra_forbidden`` and the §12 contract test failed on its first line.
    """
    resp = CapabilitiesResponse(
        tenant_exam={"id": "exam-001", "name": "CSEE 2026"},
        tenant={"id": "exam-001", "name": "CSEE 2026"},
        capabilities={"collection.push": True},
    )
    assert resp.tenant_exam.id == "exam-001"
    assert resp.tenant_exam.name == "CSEE 2026"


def test_capabilities_dump_still_emits_tenant_exam_only_when_both_were_sent():
    resp = CapabilitiesResponse.model_validate(
        {
            "tenant_exam": {"id": "exam-001"},
            "tenant": {"id": "exam-001"},
            "capabilities": {"collection.push": True},
        }
    )
    dumped = resp.model_dump(by_alias=True)
    assert "tenant_exam" in dumped
    assert "tenant" not in dumped


def test_capabilities_ignores_a_field_exametrics_adds_ahead_of_central():
    """§7.4: adding a field is a compatible change, so it must not be an outage."""
    resp = CapabilitiesResponse.model_validate(
        {
            "tenant_exam": {"id": "exam-001"},
            "capabilities": {"collection.push": True},
            "some_future_field": {"nested": [1, 2, 3]},
        }
    )
    assert "some_future_field" not in resp.model_dump()


def test_capabilities_is_the_only_model_that_ignores_extras():
    """Everything Central *sends* still fails loudly on a typo."""
    assert CapabilitiesResponse.model_config["extra"] == "ignore"
    for model in (
        ApprovalInstruction,
        CollectionChunkAck,
        CollectionCounts,
        CollectionSessionComplete,
        CollectionSessionStart,
        EntitlementState,
        EntitlementsResponse,
        ErrorBody,
        ErrorEnvelope,
        ExamProvisionRequest,
        ExamProvisionResponse,
        KeyProvisionRequest,
        KeyProvisionResponse,
        ProcessingQuoteOut,
        ProcessingRequestIn,
        ProcessingRequestOut,
        ProvisionWarning,
        QuoteOut,
        RequesterInfo,
        RowValidationDetail,
        SubjectSpec,
        TenantExamInfo,
        WebhookEnvelope,
    ):
        assert model.model_config["extra"] == "forbid", model.__name__


def test_capabilities_approval_fields_default():
    resp = CapabilitiesResponse(
        tenant_exam={"id": "exam-001"},
        capabilities={"collection.push": True},
    )
    assert resp.approval_status is None
    assert resp.approval_note is None
    assert resp.requested_scopes == []
    assert resp.usable_scopes == []
    assert resp.key_prefix is None


def test_capabilities_approval_fields_populated():
    resp = CapabilitiesResponse(
        tenant_exam={"id": "exam-001"},
        capabilities={"collection.push": True, "results.read": False},
        approval_status="PENDING",
        approval_note=None,
        requested_scopes=["collection:push", "results:read"],
        usable_scopes=["collection:push"],
        key_prefix="lz_ab12cd",
    )
    assert resp.usable_scopes == ["collection:push"]
    assert resp.key_prefix == "lz_ab12cd"


# ─── RequesterInfo ────────────────────────────────────────────────────────────────

def test_requester_info_round_trip():
    req = RequesterInfo(
        name="Asha Mwenda",
        username="amwenda",
        role="GLOBAL_ADMIN",
        user_ref="user-uuid-1",
        contact="asha@example.com",
    )
    assert req.model_dump() == {
        "name": "Asha Mwenda",
        "username": "amwenda",
        "role": "GLOBAL_ADMIN",
        "user_ref": "user-uuid-1",
        "contact": "asha@example.com",
    }


def test_requester_info_name_only():
    req = RequesterInfo(name="Asha Mwenda")
    assert req.username is None
    assert req.contact is None


def test_requester_info_requires_name():
    with pytest.raises(PydanticValidationError):
        RequesterInfo(username="amwenda")


# ─── KeyProvisionRequest / KeyProvisionResponse ───────────────────────────────────

def test_key_provision_request_minimal():
    req = KeyProvisionRequest(
        external_ref="exam-uuid-1",
        exam_name="CSEE 2026",
        exam_level="CSEE",
    )
    assert req.scopes == []
    assert req.requested_by is None
    assert req.board_name is None


def test_key_provision_request_full():
    req = KeyProvisionRequest(
        external_ref="exam-uuid-1",
        exam_name="CSEE 2026",
        exam_level="CSEE",
        board_name="Zone 1 Board",
        board_id="board-001",
        start_date="2026-06-01",
        end_date="2026-06-30",
        scopes=["collection:push", "results:read"],
        partner_label="LAZEIMS Zone 1",
        requested_by={"name": "Asha Mwenda", "role": "GLOBAL_ADMIN"},
    )
    assert req.requested_by.name == "Asha Mwenda"
    assert req.scopes == ["collection:push", "results:read"]


def test_key_provision_request_forbids_extra_fields():
    with pytest.raises(PydanticValidationError):
        KeyProvisionRequest(
            external_ref="exam-uuid-1",
            exam_name="CSEE 2026",
            exam_level="CSEE",
            api_key="never-accept-this",
        )


@pytest.mark.parametrize("missing", ["external_ref", "exam_name", "exam_level"])
def test_key_provision_request_required_fields(missing):
    payload = {
        "external_ref": "exam-uuid-1",
        "exam_name": "CSEE 2026",
        "exam_level": "CSEE",
    }
    payload.pop(missing)
    with pytest.raises(PydanticValidationError):
        KeyProvisionRequest(**payload)


def test_key_provision_response_defaults():
    resp = KeyProvisionResponse(
        api_key="lz_secret",
        key_id="key-uuid-1",
        exam_ref="exam-ref-1",
        external_ref="exam-uuid-1",
    )
    assert resp.usable_scopes == []
    assert resp.requested_scopes == []
    assert resp.exam_created is False
    assert resp.approval_status is None
    assert resp.key_prefix is None


def test_key_provision_response_full():
    resp = KeyProvisionResponse(
        api_key="lz_secret",
        key_id="key-uuid-1",
        key_prefix="lz_ab12cd",
        exam_ref="exam-ref-1",
        external_ref="exam-uuid-1",
        exam_created=True,
        requested_scopes=["collection:push", "results:process"],
        usable_scopes=["collection:push"],
        approval_status="PENDING",
        approval_note=None,
    )
    assert resp.exam_created is True
    assert resp.usable_scopes == ["collection:push"]


# ─── Entitlements (§5.2) ──────────────────────────────────────────────────────────

def test_entitlement_state_minimal():
    state = EntitlementState(state="NONE")
    assert state.reason is None
    assert state.approved_at is None
    assert state.valid_for_configuration_hash is None


def test_entitlements_response_approved_processing():
    resp = EntitlementsResponse(
        exam_ref="exm_01J8",
        closeout_revision=1,
        processing={
            "state": "APPROVED",
            "approved_at": "2026-10-31T08:15:00Z",
            "approved_by": "billing@example.com",
            "expires_at": "2026-11-30T08:15:00Z",
            "valid_for_configuration_hash": "sha256:abc",
        },
        results={"state": "LOCKED", "reason": "PROCESSING_NOT_COMPLETE"},
    )
    assert resp.processing.approved_by == "billing@example.com"
    assert resp.results.reason == "PROCESSING_NOT_COMPLETE"


def test_entitlements_response_requires_both_entitlements():
    with pytest.raises(PydanticValidationError):
        EntitlementsResponse(exam_ref="exm_01J8", processing={"state": "NONE"})


# ─── CollectionCounts / QuoteOut (§6.1) ───────────────────────────────────────────

def test_collection_counts_default_to_zero():
    counts = CollectionCounts()
    assert (counts.students, counts.centres, counts.subject_registrations) == (0, 0, 0)


def test_collection_counts_reject_negatives():
    with pytest.raises(PydanticValidationError):
        CollectionCounts(students=-1)


def test_quote_out_matches_the_worked_example_in_the_design():
    """§6.1's only concrete example: 18 432 students × 250 = 4 608 000 TZS."""
    quote = QuoteOut(
        amount=4_608_000,
        unit="per_student",
        unit_amount=250,
        billable_students=18_432,
        centres=96,
        subject_registrations=121_004,
        expires_at="2026-11-05T00:00:00Z",
    )
    assert quote.currency == "TZS"
    assert quote.amount == quote.billable_students * quote.unit_amount


def test_quote_out_reports_all_three_counts_so_the_unit_can_change_later():
    quote = QuoteOut(amount=750, unit="per_student", unit_amount=250, billable_students=3)
    assert quote.centres is None
    assert quote.subject_registrations is None


def test_quote_out_rejects_a_negative_amount():
    with pytest.raises(PydanticValidationError):
        QuoteOut(amount=-1, unit="per_student", unit_amount=250, billable_students=0)


def test_quote_out_rejects_a_non_three_letter_currency():
    with pytest.raises(PydanticValidationError):
        QuoteOut(
            currency="SHILLING",
            amount=0,
            unit="per_run",
            unit_amount=0,
            billable_students=0,
        )


# ─── ProcessingRequestIn / ProcessingQuoteOut / ProcessingRequestOut (§6.1, D10) ───

def test_processing_request_in_minimal():
    req = ProcessingRequestIn(
        external_ref="9c1f-uuid",
        closeout_revision=1,
        configuration_hash="sha256:abc",
    )
    assert req.counts.students == 0
    assert req.requested_by is None
    assert req.note is None


def test_processing_request_in_full():
    req = ProcessingRequestIn(
        external_ref="9c1f-uuid",
        closeout_revision=2,
        configuration_hash="sha256:abc",
        counts={"students": 18432, "centres": 96, "subject_registrations": 121004},
        requested_by={"name": "A. Mwita", "role": "EXAM_ADMIN"},
        note="FTNA 2026 final submission",
    )
    assert req.counts.subject_registrations == 121004
    assert req.requested_by.name == "A. Mwita"


def test_processing_request_in_binds_to_a_revision_and_a_hash():
    """§5.2: without both, one approval could be reused after a reopen."""
    for missing in ("closeout_revision", "configuration_hash"):
        payload = {
            "external_ref": "9c1f-uuid",
            "closeout_revision": 1,
            "configuration_hash": "sha256:abc",
        }
        payload.pop(missing)
        with pytest.raises(PydanticValidationError):
            ProcessingRequestIn(**payload)


def test_processing_request_in_no_longer_accepts_the_placeholder_shape():
    """D10 reuses the name for §6.1's real shape; force/dry_run never went on a wire."""
    with pytest.raises(PydanticValidationError):
        ProcessingRequestIn(exam_ref="exam-001", force=True, dry_run=True)


def test_processing_quote_out_is_the_202_body():
    out = ProcessingQuoteOut(
        request_id="prq_01J8",
        state="PENDING_APPROVAL",
        quote={
            "amount": 750,
            "unit": "per_student",
            "unit_amount": 250,
            "billable_students": 3,
        },
        approval={"instructions_url": "https://exametrics.example/approvals/prq_01J8"},
        next_poll_after="2026-10-31T06:00:00Z",
    )
    assert out.approval.method == "EXAMETRICS_CONSOLE"
    assert out.quote.amount == 750
    assert out.replayed is False


def test_processing_quote_out_requires_a_quote():
    with pytest.raises(PydanticValidationError):
        ProcessingQuoteOut(request_id="prq_01J8", state="PENDING_APPROVAL")


def test_processing_quote_out_marks_an_idempotency_replay():
    out = ProcessingQuoteOut(
        request_id="prq_01J8",
        state="PENDING_APPROVAL",
        quote={"amount": 0, "unit": "per_run", "unit_amount": 0, "billable_students": 0},
        replayed=True,
    )
    assert out.replayed is True


def test_processing_request_out_minimal():
    out = ProcessingRequestOut(
        request_id="prq_01J8",
        exam_ref="exm_01J8",
        external_ref="9c1f-uuid",
        closeout_revision=1,
        configuration_hash="sha256:abc",
        state="PENDING_APPROVAL",
    )
    assert out.quote is None
    assert out.run_id is None
    assert out.billable_count is None


def test_processing_request_out_carries_the_frozen_billable_count():
    out = ProcessingRequestOut(
        request_id="prq_01J8",
        exam_ref="exm_01J8",
        external_ref="9c1f-uuid",
        closeout_revision=1,
        configuration_hash="sha256:abc",
        state="APPROVED",
        billable_count=18432,
        run_id="run_01J8",
        decided_by="billing@example.com",
    )
    assert out.billable_count == 18432
    assert out.run_id == "run_01J8"


def test_approval_instruction_defaults_to_the_console():
    approval = ApprovalInstruction()
    assert approval.method == "EXAMETRICS_CONSOLE"
    assert approval.instructions_url is None


# ─── Chunked collection upload (§7.2) ─────────────────────────────────────────────

def test_collection_session_start_tracks_what_has_landed():
    start = CollectionSessionStart(
        session_id="cus_01J8",
        exam_ref="exm_01J8",
        external_ref="9c1f-uuid",
        chunk_count=4,
        max_rows_per_chunk=5000,
        expected_digest="sha256:abc",
        received_chunks=[0, 1],
        expires_at="2026-11-01T00:00:00Z",
    )
    assert start.received_chunks == [0, 1]


def test_collection_session_start_defaults_to_nothing_received():
    start = CollectionSessionStart(
        session_id="cus_01J8", exam_ref="exm_01J8", chunk_count=0, max_rows_per_chunk=5000
    )
    assert start.received_chunks == []
    assert start.expected_digest is None


def test_collection_session_start_rejects_a_zero_chunk_size():
    with pytest.raises(PydanticValidationError):
        CollectionSessionStart(
            session_id="cus_01J8", exam_ref="exm_01J8", chunk_count=1, max_rows_per_chunk=0
        )


def test_collection_chunk_ack():
    ack = CollectionChunkAck(
        session_id="cus_01J8",
        chunk_index=2,
        rows=5000,
        digest="sha256:abc",
        received_chunks=[0, 1, 2],
        remaining_chunks=1,
    )
    assert ack.remaining_chunks == 1


def test_collection_session_complete_reports_the_verification_outcome():
    done = CollectionSessionComplete(
        session_id="cus_01J8",
        exam_ref="exm_01J8",
        chunk_count=4,
        total_rows=18432,
        digest="sha256:abc",
        digest_verified=True,
        report={"students": 18432},
    )
    assert done.digest_verified is True
    assert done.replayed is False


def test_collection_session_complete_can_report_a_digest_mismatch():
    done = CollectionSessionComplete(
        session_id="cus_01J8",
        exam_ref="exm_01J8",
        chunk_count=4,
        total_rows=18431,
        digest="sha256:def",
        digest_verified=False,
    )
    assert done.digest_verified is False
    assert done.report is None


# ─── WebhookEnvelope (§7.3) ───────────────────────────────────────────────────────

def test_webhook_envelope_full():
    hook = WebhookEnvelope(
        event="processing.completed",
        exam_ref="exm_01J8",
        external_ref="9c1f-uuid",
        request_id="prq_01J8",
        state="COMPLETED",
        occurred_at="2026-10-31T09:02:11Z",
        signature="hmac-sha256:deadbeef",
    )
    assert hook.event == "processing.completed"


def test_webhook_envelope_minimal():
    """results.ready carries no request_id, so only event/exam_ref/occurred_at bind."""
    hook = WebhookEnvelope(
        event="results.ready", exam_ref="exm_01J8", occurred_at="2026-10-31T09:02:11Z"
    )
    assert hook.request_id is None
    assert hook.signature is None


def test_webhook_envelope_requires_an_occurred_at():
    with pytest.raises(PydanticValidationError):
        WebhookEnvelope(event="results.ready", exam_ref="exm_01J8")


# ─── ErrorEnvelope / RowValidationDetail (§8) ─────────────────────────────────────

def test_row_validation_detail_is_row_addressable():
    row = RowValidationDetail(
        student_id="S0201-0001",
        code="MARK_ABOVE_MAXIMUM",
        message="Theory mark 38.0 exceeds the maximum 30.0.",
        subject_code="032",
        paper="THEORY2",
    )
    assert row.student_id == "S0201-0001"
    assert row.paper == "THEORY2"


def test_row_validation_detail_paper_is_optional():
    row = RowValidationDetail(
        student_id="S0201-0001", code="NOT_REGISTERED", message="Not registered."
    )
    assert row.subject_code is None
    assert row.paper is None


def test_row_validation_detail_requires_the_row_address():
    with pytest.raises(PydanticValidationError):
        RowValidationDetail(code="NOT_REGISTERED", message="Not registered.")


def test_error_envelope_with_row_details():
    envelope = ErrorEnvelope(
        error={
            "code": "VALIDATION_FAILED",
            "message": "1 row rejected.",
            "details": [
                {
                    "student_id": "S0201-0001",
                    "code": "MARK_ABOVE_MAXIMUM",
                    "message": "Too high.",
                }
            ],
            "request_id": "req_01J8",
        }
    )
    assert envelope.error.code == "VALIDATION_FAILED"
    assert RowValidationDetail.model_validate(envelope.error.details[0]).student_id


def test_error_envelope_details_may_be_a_mapping():
    """Most codes carry context, not rows — e.g. APPROVAL_REQUIRED's request_id."""
    envelope = ErrorEnvelope(
        error={
            "code": "APPROVAL_REQUIRED",
            "message": "Processing needs approval before it can run.",
            "details": {"request_id": "prq_01J8", "state": "PENDING_APPROVAL"},
        }
    )
    assert envelope.error.details["state"] == "PENDING_APPROVAL"


def test_error_envelope_requires_a_code_and_message():
    with pytest.raises(PydanticValidationError):
        ErrorEnvelope(error={"message": "something went wrong"})


def test_error_body_defaults():
    body = ErrorBody(code="RATE_LIMITED", message="Slow down.")
    assert body.details is None
    assert body.request_id is None


# ─── SubjectSpec ──────────────────────────────────────────────────────────────────

def test_subject_spec_minimal():
    s = SubjectSpec(subject_code="011", subject_name="CIVICS")
    assert s.has_practical is False
    assert s.has_theory_2 is False
    assert s.subject_short is None
    assert s.theory_max is None
    assert (s.is_primary, s.is_olevel, s.is_alevel) == (False, False, False)


def test_subject_spec_empty_code_rejected():
    with pytest.raises(PydanticValidationError):
        SubjectSpec(subject_code="", subject_name="CIVICS")


def test_subject_spec_carries_the_maxima_exametrics_grades_against():
    s = SubjectSpec(
        subject_code="032",
        subject_name="PHYSICS",
        subject_short="032",
        has_theory_2=True,
        has_practical=True,
        theory_max=50,
        theory_2_max=30,
        practical_max=20,
        is_olevel=True,
    )
    assert s.theory_max == 50.0
    assert s.theory_2_max == 30.0
    assert s.practical_max == 20.0
    assert s.is_olevel is True


def test_subject_spec_rejects_a_negative_maximum():
    with pytest.raises(PydanticValidationError):
        SubjectSpec(subject_code="011", subject_name="CIVICS", theory_max=-1)


def test_subject_spec_accepts_a_collection_payload_subject_row_verbatim():
    """§1.3 and §4.2 name the same fields; one model must serve both calls."""
    row = {
        "subject_code": "011",
        "subject_name": "HISTORY",
        "subject_short": "011",
        "has_theory_2": False,
        "has_practical": False,
        "theory_max": 100.0,
        "theory_2_max": None,
        "practical_max": None,
        "is_primary": False,
        "is_olevel": True,
        "is_alevel": False,
    }
    assert SubjectSpec.model_validate(row).subject_code == "011"


# ─── Import from top-level schemas module ────────────────────────────────────────

def test_schemas_re_export():
    from lazeims_common import schemas

    for name in (
        "ApprovalInstruction",
        "CapabilitiesResponse",
        "CollectionChunkAck",
        "CollectionCounts",
        "CollectionSessionComplete",
        "CollectionSessionStart",
        "EntitlementState",
        "EntitlementsResponse",
        "ErrorBody",
        "ErrorEnvelope",
        "ExamProvisionRequest",
        "ExamProvisionResponse",
        "KeyProvisionRequest",
        "KeyProvisionResponse",
        "ProcessingQuoteOut",
        "ProcessingRequestIn",
        "ProcessingRequestOut",
        "ProvisionWarning",
        "QuoteOut",
        "RequesterInfo",
        "RowValidationDetail",
        "SubjectSpec",
        "TenantExamInfo",
        "TenantInfo",
        "WebhookEnvelope",
    ):
        assert name in schemas.__all__, name
        assert getattr(schemas, name) is globals()[name], name
