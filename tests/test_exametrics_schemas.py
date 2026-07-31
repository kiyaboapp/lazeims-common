"""Tests for the ExaMetrics integration contract schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from lazeims_common import EXAMETRICS_INTEGRATION_CONTRACT
from lazeims_common.schemas.exametrics import (
    CONTRACT_VERSION,
    CapabilitiesResponse,
    ExamProvisionRequest,
    ExamProvisionResponse,
    KeyProvisionRequest,
    KeyProvisionResponse,
    ProcessingQuoteOut,
    ProcessingRequestIn,
    RequesterInfo,
    SubjectSpec,
    TenantExamInfo,
    TenantInfo,
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
        warnings=["Configuration hash mismatch", "Subject 099 not recognized"],
    )
    assert len(resp.warnings) == 2
    assert resp.configuration_accepted is False


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


# ─── ProcessingRequestIn / ProcessingQuoteOut ─────────────────────────────────────

def test_processing_request_defaults():
    req = ProcessingRequestIn(exam_ref="exam-001")
    assert req.force is False
    assert req.dry_run is False


def test_processing_request_dry_run():
    req = ProcessingRequestIn(exam_ref="exam-001", dry_run=True)
    assert req.dry_run is True


def test_processing_quote_out():
    quote = ProcessingQuoteOut(
        exam_ref="exam-001",
        student_count=500,
        estimated_duration_seconds=120,
        cost_units=2.5,
        accepted=False,
        task_id=None,
    )
    assert quote.student_count == 500
    assert quote.accepted is False


def test_processing_quote_accepted():
    quote = ProcessingQuoteOut(
        exam_ref="exam-001",
        student_count=1000,
        accepted=True,
        task_id="task-uuid-789",
    )
    assert quote.accepted is True
    assert quote.task_id == "task-uuid-789"


def test_processing_quote_negative_student_count_rejected():
    with pytest.raises(PydanticValidationError):
        ProcessingQuoteOut(
            exam_ref="exam-001",
            student_count=-1,
            accepted=True,
        )


# ─── SubjectSpec ──────────────────────────────────────────────────────────────────

def test_subject_spec_minimal():
    s = SubjectSpec(subject_code="011", subject_name="CIVICS")
    assert s.has_practical is False
    assert s.has_theory_2 is False


def test_subject_spec_empty_code_rejected():
    with pytest.raises(PydanticValidationError):
        SubjectSpec(subject_code="", subject_name="CIVICS")


# ─── Import from top-level schemas module ────────────────────────────────────────

def test_schemas_re_export():
    from lazeims_common.schemas import (
        CapabilitiesResponse as CR,
        ExamProvisionRequest as EPR,
        ExamProvisionResponse as EPRSP,
        KeyProvisionRequest as KPRQ,
        KeyProvisionResponse as KPRS,
        ProcessingQuoteOut as PQO,
        ProcessingRequestIn as PRI,
        RequesterInfo as RI,
        SubjectSpec as SS,
        TenantExamInfo as TEI,
        TenantInfo as TI,
    )
    assert CR is CapabilitiesResponse
    assert EPR is ExamProvisionRequest
    assert EPRSP is ExamProvisionResponse
    assert KPRQ is KeyProvisionRequest
    assert KPRS is KeyProvisionResponse
    assert PQO is ProcessingQuoteOut
    assert PRI is ProcessingRequestIn
    assert RI is RequesterInfo
    assert SS is SubjectSpec
    assert TEI is TenantExamInfo
    assert TI is TenantInfo
