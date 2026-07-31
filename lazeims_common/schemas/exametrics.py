"""Versioned ExaMetrics integration contract schemas (``exametrics-integration/v2``).

Shared between the zone partner (LAZEIMS) and ExaMetrics (backend-sis) so both
sides validate identically and cannot silently drift apart.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "exametrics-integration/v2"


# ─── Exam provisioning ───────────────────────────────────────────────────────────

class SubjectSpec(BaseModel):
    """Minimal subject definition sent during provisioning."""

    model_config = ConfigDict(extra="forbid")

    subject_code: str = Field(..., min_length=1, max_length=20)
    subject_name: str = Field(..., min_length=1, max_length=100)
    has_practical: bool = False
    has_theory_2: bool = False


class ExamProvisionRequest(BaseModel):
    """PUT /integration/exams provisioning payload.

    Sent by the zone partner's server when it creates or updates an exam
    on the ExaMetrics side.
    """

    model_config = ConfigDict(extra="forbid")

    external_ref: str = Field(..., min_length=1, max_length=64, description="Partner's own exam identifier.")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable exam name.")
    exam_code: Optional[str] = Field(None, max_length=30, description="Short code (e.g. CSEE-2026).")
    level: str = Field(..., description="Exam level: STNA | SFNA | PSLE | FTNA | CSEE | ACSEE")
    board: Optional[str] = Field(None, max_length=64, description="Board/organisation ID.")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    zone_name: Optional[str] = Field(None, max_length=100, description="Zone or region name.")
    filling_mode: Optional[str] = Field(None, description="ITEM_LEVEL | TOTAL_MARKS")
    rules_version: str = Field(default="1.0", description="Rules version the partner expects.")
    configuration_hash: Optional[str] = Field(
        None, max_length=128,
        description="SHA-256 of the exam configuration the partner holds.",
    )
    subjects: List[SubjectSpec] = Field(default_factory=list)


class ExamProvisionResponse(BaseModel):
    """Response to a successful provisioning request."""

    model_config = ConfigDict(extra="forbid")

    exam_ref: str = Field(..., description="ExaMetrics-side exam ID.")
    external_ref: str = Field(..., description="Echo of the partner's external_ref.")
    state: str = Field(..., description="CREATED | UPDATED | UNCHANGED")
    created: bool = Field(..., description="True if a new exam was provisioned.")
    configuration_accepted: bool = Field(
        default=True,
        description="False when the configuration_hash doesn't match, suggesting a re-sync.",
    )
    warnings: List[str] = Field(default_factory=list)


# ─── Capabilities (GET /integration/me) ──────────────────────────────────────────

class TenantInfo(BaseModel):
    """Minimal tenant (exam) info returned in capabilities response."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="ExaMetrics exam ID the key is scoped to.")
    name: Optional[str] = Field(None, description="Human-readable exam name.")
    environment: str = Field(default="production", description="Deployment environment.")


class CapabilitiesResponse(BaseModel):
    """GET /integration/me response.

    Tells a partner what their key can do, the contract version in use,
    applicable limits, and supported rules versions.
    """

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    tenant: TenantInfo
    capabilities: Dict[str, bool] = Field(
        ...,
        description=(
            "Map of capability names to whether they are currently enabled. "
            "Keys: exam.provision, collection.push, registrations.extract, "
            "exam.read, processing.request, processing.execute, results.read, "
            "results.download"
        ),
    )
    limits: Dict[str, Any] = Field(
        default_factory=dict,
        description="Rate limits and size constraints for this key.",
    )
    supported_rules_versions: List[str] = Field(
        default_factory=lambda: ["1.0"],
        description="Rules versions this ExaMetrics deployment supports.",
    )


# ─── Processing request / quote ──────────────────────────────────────────────────

class ProcessingRequestIn(BaseModel):
    """Request to trigger or quote results processing."""

    model_config = ConfigDict(extra="forbid")

    exam_ref: str = Field(..., description="ExaMetrics exam ID.")
    force: bool = Field(default=False, description="Force re-processing even if already processed.")
    dry_run: bool = Field(default=False, description="If true, return a quote without triggering.")


class ProcessingQuoteOut(BaseModel):
    """Quote or acknowledgement for a processing request."""

    model_config = ConfigDict(extra="forbid")

    exam_ref: str
    student_count: int = Field(..., ge=0)
    estimated_duration_seconds: Optional[int] = Field(None, ge=0)
    cost_units: Optional[float] = Field(None, ge=0, description="Cost in billing units (if applicable).")
    accepted: bool = Field(..., description="True if processing was triggered (not a dry_run).")
    task_id: Optional[str] = Field(None, description="Background task ID if accepted.")
