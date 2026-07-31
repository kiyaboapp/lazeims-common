"""Versioned ExaMetrics integration contract schemas (``exametrics-integration/v2``).

Shared between the zone partner (LAZEIMS) and ExaMetrics (backend-sis) so both
sides validate identically and cannot silently drift apart.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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

class TenantExamInfo(BaseModel):
    """The ExaMetrics exam account a key is scoped to.

    Named ``TenantExamInfo`` (never bare "tenant") because "tenant" already
    means *a subscribing school* elsewhere in the platform
    (``TenantSchool``/``shuleyetu_tenant_schools``).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="ExaMetrics exam ID the key is scoped to.")
    name: Optional[str] = Field(None, description="Human-readable exam name.")
    environment: str = Field(default="production", description="Deployment environment.")


#: Deprecated alias kept for one release so existing importers keep working.
#: Use :class:`TenantExamInfo`.
TenantInfo = TenantExamInfo


class CapabilitiesResponse(BaseModel):
    """GET /integration/me response.

    Tells a partner what their key can do, the contract version in use,
    applicable limits, and supported rules versions.

    ``tenant_exam`` accepts the legacy ``tenant`` wire key for one release
    (backend-sis and Central deploy independently) but only ever serialises
    ``tenant_exam``.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    contract_version: str = Field(default=CONTRACT_VERSION)
    tenant_exam: TenantExamInfo = Field(
        ...,
        validation_alias=AliasChoices("tenant_exam", "tenant"),
        serialization_alias="tenant_exam",
        description="The ExaMetrics exam account this key is scoped to.",
    )
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
    approval_status: Optional[str] = Field(
        None,
        description="Approval state of the commercial scopes: PENDING | APPROVED | REJECTED | NOT_REQUIRED.",
    )
    approval_note: Optional[str] = Field(
        None, description="Reviewer note, populated when approval_status is REJECTED."
    )
    requested_scopes: List[str] = Field(
        default_factory=list, description="Scopes the partner asked for."
    )
    usable_scopes: List[str] = Field(
        default_factory=list,
        description="Subset of requested_scopes usable right now (free scopes plus approved paid ones).",
    )
    key_prefix: Optional[str] = Field(
        None,
        description="Non-secret leading fragment of the key, safe to display for support.",
    )


# ─── Key provisioning (POST /integration/provision) ──────────────────────────────

class RequesterInfo(BaseModel):
    """Identity of the partner-side operator who asked for a key.

    Resolved server-side from the session user, never supplied by a browser,
    so it cannot be forged. Distinct from ExaMetrics' own ``created_by`` user FK.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=150, description="Full name of the requester.")
    username: Optional[str] = Field(None, max_length=150)
    role: Optional[str] = Field(None, max_length=50)
    user_ref: Optional[str] = Field(None, max_length=64, description="Partner-side user identifier.")
    contact: Optional[str] = Field(None, max_length=150, description="Email or phone number.")


class KeyProvisionRequest(BaseModel):
    """POST /integration/provision payload.

    Sent server-to-server by the partner's backend (authenticated with the zone
    enrolment secret, not an API key) so no human ever handles the issued key.
    """

    model_config = ConfigDict(extra="forbid")

    external_ref: str = Field(..., min_length=1, max_length=64, description="Partner's own exam identifier.")
    exam_name: str = Field(..., min_length=1, max_length=150, description="Human-readable exam name.")
    exam_level: str = Field(..., min_length=1, max_length=20, description="STNA | SFNA | PSLE | FTNA | CSEE | ACSEE")
    board_name: Optional[str] = Field(
        None, max_length=150,
        description="Board name; resolved or created on the ExaMetrics side when board_id is absent.",
    )
    board_id: Optional[str] = Field(None, max_length=64, description="ExaMetrics board ID, when already known.")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    scopes: List[str] = Field(
        default_factory=list,
        description="Scopes requested. Free scopes are granted immediately, paid ones queue for approval.",
    )
    partner_label: Optional[str] = Field(None, max_length=100, description="Label for the issued key.")
    requested_by: Optional[RequesterInfo] = None


class KeyProvisionResponse(BaseModel):
    """Response to a successful provisioning request.

    ``api_key`` is returned exactly once, server-to-server only: it is never
    placed in a response a browser can read and never written to an audit record.
    """

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(..., description="The secret, returned once, server-to-server only.")
    key_id: str = Field(..., description="ExaMetrics ID of the issued key record.")
    key_prefix: Optional[str] = Field(None, description="Non-secret leading fragment, safe to display.")
    exam_ref: str = Field(..., description="ExaMetrics-side exam ID.")
    external_ref: str = Field(..., description="Echo of the partner's external_ref.")
    exam_created: bool = Field(default=False, description="True if a new exam was provisioned.")
    requested_scopes: List[str] = Field(default_factory=list)
    usable_scopes: List[str] = Field(
        default_factory=list, description="Scopes usable immediately, without waiting for approval."
    )
    approval_status: Optional[str] = Field(
        None, description="PENDING | APPROVED | REJECTED | NOT_REQUIRED"
    )
    approval_note: Optional[str] = None


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
