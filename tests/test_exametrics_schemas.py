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
    ProcessingQuoteOut,
    ProcessingRequestIn,
    SubjectSpec,
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
        ProcessingQuoteOut as PQO,
        ProcessingRequestIn as PRI,
        SubjectSpec as SS,
        TenantInfo as TI,
    )
    assert CR is CapabilitiesResponse
    assert EPR is ExamProvisionRequest
    assert EPRSP is ExamProvisionResponse
    assert PQO is ProcessingQuoteOut
    assert PRI is ProcessingRequestIn
    assert SS is SubjectSpec
    assert TI is TenantInfo
