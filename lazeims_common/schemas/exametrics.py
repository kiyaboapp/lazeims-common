"""Versioned ExaMetrics integration contract schemas (``exametrics-integration/v2``).

Shared between the zone partner (LAZEIMS) and ExaMetrics (backend-sis) so both
sides validate identically and cannot silently drift apart.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

CONTRACT_VERSION = "exametrics-integration/v2"


# ─── Exam provisioning ───────────────────────────────────────────────────────────

class SubjectSpec(BaseModel):
    """Subject definition sent during provisioning (§4.2).

    Carries the per-paper maxima and level flags because ExaMetrics grades
    against them: without ``theory_max`` the same raw mark means different
    things on the two sides of the boundary. The field names and types match
    the ``subjects`` rows of the collection payload (§1.3) exactly, so one
    definition serves both calls.
    """

    model_config = ConfigDict(extra="forbid")

    subject_code: str = Field(..., min_length=1, max_length=20)
    subject_name: str = Field(..., min_length=1, max_length=100)
    subject_short: Optional[str] = Field(
        None, max_length=20, description="Short display code; defaults to subject_code on the server."
    )
    has_practical: bool = False
    has_theory_2: bool = False
    theory_max: Optional[float] = Field(None, ge=0, description="Maximum mark for paper 1 (theory).")
    theory_2_max: Optional[float] = Field(None, ge=0, description="Maximum mark for paper 2, when has_theory_2.")
    practical_max: Optional[float] = Field(None, ge=0, description="Maximum practical mark, when has_practical.")
    is_primary: bool = False
    is_olevel: bool = False
    is_alevel: bool = False


class ProvisionWarning(BaseModel):
    """A non-fatal difference ExaMetrics reconciled during an upsert (§4.2).

    Structured rather than a bare string so the operator UI can address the
    offending subject instead of printing prose.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64, description="e.g. SUBJECT_MAX_MARKS_DIFFERS")
    message: str = Field(..., min_length=1)
    subject_code: Optional[str] = Field(None, max_length=20)
    field: Optional[str] = Field(None, max_length=64, description="Field the difference applies to.")


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
    warnings: List[ProvisionWarning] = Field(default_factory=list)


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

    This is the **only** model in this contract with ``extra="ignore"``, and it
    is deliberate: backend-sis's ``identity_payload()`` emits ``tenant_exam``
    *and* a byte-identical deprecated ``tenant`` mirror in the same body. Under
    ``extra="forbid"`` the mirror is consumed as an unexpected extra (the alias
    only ever fills one field) and validating the genuine payload raises
    ``extra_forbidden``. Ignoring extras also means a field ExaMetrics adds
    ahead of Central is a no-op rather than an outage — which is exactly the
    §7.4 rule that adding a field is a compatible change. Every other model
    keeps ``forbid`` so a typo in something Central *sends* is still caught.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

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


# ─── Entitlements (GET /integration/exams/{ref}/entitlements) ────────────────────

class EntitlementState(BaseModel):
    """One entitlement's current state (§5.2).

    Used for both the ``processing`` and the ``results`` entitlement. The
    approval-provenance fields are only populated for ``processing``; ``results``
    normally carries just ``state`` plus a machine-readable ``reason`` so the UI
    can distinguish *not yet* from *not allowed* (§13.4).
    """

    model_config = ConfigDict(extra="forbid")

    state: str = Field(
        ...,
        description=(
            "NONE | PENDING_APPROVAL | APPROVED | REJECTED | EXPIRED | "
            "AVAILABLE | LOCKED"
        ),
    )
    reason: Optional[str] = Field(
        None,
        description="Machine-readable blocker, e.g. PROCESSING_NOT_COMPLETE | SCOPE_NOT_GRANTED.",
    )
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = Field(None, max_length=150)
    expires_at: Optional[datetime] = None
    valid_for_configuration_hash: Optional[str] = Field(
        None, max_length=128,
        description="Approval is bound to this configuration hash; a mismatch requires re-approval.",
    )


class EntitlementsResponse(BaseModel):
    """GET /integration/exams/{exam_ref}/entitlements response (§5.2)."""

    model_config = ConfigDict(extra="forbid")

    exam_ref: str
    closeout_revision: Optional[int] = Field(None, ge=0)
    processing: EntitlementState
    results: EntitlementState


# ─── Processing request / quote (§6.1) ───────────────────────────────────────────

class CollectionCounts(BaseModel):
    """The three counts a quote is expressed in.

    When these arrive from a client they are **display and comparison only** —
    §6.2 requires the price to be recomputed from the pushed collection, never
    derived from a number the client can inflate.
    """

    model_config = ConfigDict(extra="forbid")

    students: int = Field(default=0, ge=0)
    centres: int = Field(default=0, ge=0)
    subject_registrations: int = Field(default=0, ge=0)


class QuoteOut(BaseModel):
    """A server-computed price for one processing run (§6.1).

    ``amount`` is in **minor units** of ``currency`` and is authoritative;
    ``unit``/``unit_amount`` are reported so the operator can see how it was
    derived, and all three counts are reported so switching the billing unit
    later is a config change rather than a contract change (§14.2a).
    """

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="TZS", min_length=3, max_length=3)
    amount: int = Field(..., ge=0, description="Total price in minor units of currency.")
    unit: str = Field(..., description="per_student | per_subject_registration | per_run")
    unit_amount: int = Field(..., ge=0, description="Price of one unit, in minor units.")
    billable_students: int = Field(..., ge=0, description="Students the price was computed over.")
    centres: Optional[int] = Field(None, ge=0)
    subject_registrations: Optional[int] = Field(None, ge=0)
    expires_at: Optional[datetime] = Field(
        None, description="After this the quote is EXPIRED and must be re-requested."
    )


class ApprovalInstruction(BaseModel):
    """How and by whom a pending request gets approved (§6.1, §14.3)."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(default="EXAMETRICS_CONSOLE", description="Approval channel.")
    instructions_url: Optional[str] = Field(
        None, description="Where the approver completes the approval."
    )
    approver: Optional[str] = Field(
        None, max_length=150, description="Who must approve, for §13.3 (name the blocker)."
    )


class ProcessingRequestIn(BaseModel):
    """POST /integration/exams/{exam_ref}/processing-requests body (§6.1).

    Re-shaped in place from the earlier ``force``/``dry_run`` placeholder: no
    deployed client ever sent that shape, so the contract version is unchanged
    (see D10). ``exam_ref`` is not a field — it is the path segment.
    """

    model_config = ConfigDict(extra="forbid")

    external_ref: str = Field(..., min_length=1, max_length=64, description="Partner's own exam identifier.")
    closeout_revision: int = Field(..., ge=0, description="Revision the approval will be bound to.")
    configuration_hash: str = Field(
        ..., min_length=1, max_length=128, description="Configuration the approval will be bound to.",
    )
    counts: CollectionCounts = Field(
        default_factory=CollectionCounts,
        description="Client's own counts — stored for display and comparison, never priced (§6.2).",
    )
    requested_by: Optional[RequesterInfo] = None
    note: Optional[str] = Field(None, max_length=500)


class ProcessingQuoteOut(BaseModel):
    """202 body of POST .../processing-requests (§6.1).

    Re-shaped in place alongside :class:`ProcessingRequestIn` (D10). The quote is
    the server's, echoed verbatim by the operator UI so the price is stated
    before the click (§13.2).
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(..., description="ExaMetrics request id, e.g. prq_01J8…")
    state: str = Field(
        ...,
        description="PENDING_APPROVAL | APPROVED | REJECTED | EXPIRED | RUNNING | COMPLETED | FAILED",
    )
    quote: QuoteOut
    approval: ApprovalInstruction = Field(default_factory=ApprovalInstruction)
    next_poll_after: Optional[datetime] = Field(
        None, description="Earliest useful poll time; polling is the authoritative fallback (§7.3)."
    )
    replayed: bool = Field(
        default=False, description="True when this is an Idempotency-Key replay (§7.1)."
    )


class ProcessingRequestOut(BaseModel):
    """A stored processing request, as returned when listing or polling one.

    Mirrors the ``exam_processing_requests`` row so Central can cache it and the
    approval console can render it without a second call.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str
    exam_ref: str
    external_ref: str
    closeout_revision: int = Field(..., ge=0)
    configuration_hash: str = Field(..., max_length=128)
    state: str
    quote: Optional[QuoteOut] = None
    counts: Optional[CollectionCounts] = Field(
        None, description="The client-supplied counts, kept for comparison only."
    )
    billable_count: Optional[int] = Field(
        None, ge=0, description="Server-computed count the approved amount was frozen against (§14.4b).",
    )
    requested_by: Optional[RequesterInfo] = None
    note: Optional[str] = None
    run_id: Optional[str] = Field(None, description="Stable run id; a replay returns the same one.")
    requested_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = Field(None, max_length=150)
    decision_reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    next_poll_after: Optional[datetime] = None


# ─── Chunked collection upload (§7.2) ────────────────────────────────────────────

class CollectionSessionStart(BaseModel):
    """Response to POST /integration/exams/{exam_ref}/collection-sessions.

    Opens a resumable upload. ``received_chunks`` is echoed on every message of
    the session so a client that lost its connection can resume without
    re-sending what already landed.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    exam_ref: str
    external_ref: Optional[str] = None
    chunk_count: int = Field(..., ge=0, description="Chunks the client declared it will send.")
    max_rows_per_chunk: int = Field(..., ge=1)
    expected_digest: Optional[str] = Field(
        None, max_length=80,
        description="Digest the client declared for the whole payload; verified on complete.",
    )
    received_chunks: List[int] = Field(default_factory=list)
    expires_at: Optional[datetime] = None


class CollectionChunkAck(BaseModel):
    """Response to PUT /integration/collection-sessions/{id}/chunks/{n}."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    chunk_index: int = Field(..., ge=0)
    rows: int = Field(..., ge=0, description="Rows accepted from this chunk.")
    digest: str = Field(..., description="Digest of this chunk alone, as sha256:…")
    received_chunks: List[int] = Field(default_factory=list)
    remaining_chunks: int = Field(default=0, ge=0)


class CollectionSessionComplete(BaseModel):
    """Response to POST /integration/collection-sessions/{id}/complete.

    ``digest`` is recomputed by the server over the reassembled canonical
    payload; ``digest_verified`` says whether it matched the client's declared
    digest. Both sides derive it from
    :func:`lazeims_common.exametrics_digest.collection_digest`, so a mismatch
    means the data differs, never that the two implementations differ.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str
    exam_ref: str
    chunk_count: int = Field(..., ge=0)
    total_rows: int = Field(..., ge=0)
    digest: str = Field(..., description="Server-computed digest of the reassembled payload.")
    digest_verified: bool
    replayed: bool = Field(default=False)
    report: Optional[Dict[str, Any]] = Field(
        None, description="The same ingest report a single-shot collection push returns."
    )


# ─── Webhooks (§7.3) ─────────────────────────────────────────────────────────────

class WebhookEnvelope(BaseModel):
    """The body ExaMetrics POSTs to the partner's callback URL (§7.3).

    Webhooks are an accelerator only: every state they announce is also
    reachable by polling, so a webhook that never arrives delays nothing
    permanently (§14.6). ``signature`` is an HMAC-SHA256 over the canonical JSON
    of this body with ``signature`` removed.
    """

    model_config = ConfigDict(extra="forbid")

    event: str = Field(
        ...,
        description=(
            "processing.completed | processing.approval_changed | "
            "processing.failed | results.ready"
        ),
    )
    exam_ref: str
    external_ref: Optional[str] = None
    request_id: Optional[str] = None
    state: Optional[str] = None
    occurred_at: datetime
    signature: Optional[str] = Field(
        None, description="hmac-sha256:… over the canonical JSON of this body without `signature`.",
    )


# ─── Error contract (§8) ─────────────────────────────────────────────────────────

class RowValidationDetail(BaseModel):
    """One row-addressable validation failure (§8).

    Every 422 carries these so the operator UI can point at the offending
    candidate instead of showing a wall of text (§13.3).
    """

    model_config = ConfigDict(extra="forbid")

    student_id: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1)
    subject_code: Optional[str] = Field(None, max_length=20)
    paper: Optional[str] = Field(
        None, max_length=20, description="THEORY1 | THEORY2 | PRACTICAL, when paper-specific."
    )


class ErrorBody(BaseModel):
    """The ``error`` object inside :class:`ErrorEnvelope`."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1)
    details: Optional[Any] = Field(
        None,
        description=(
            "Code-specific context: a mapping for most codes, or a list of "
            "RowValidationDetail for VALIDATION_FAILED."
        ),
    )
    request_id: Optional[str] = None


class ErrorEnvelope(BaseModel):
    """The error envelope both sides emit (§8), mirroring Central's ``app/main.py``."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
