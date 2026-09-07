"""Versioned station sync contract (``station-sync/v1``).

Request: station -> Central, a bounded batch of ordered events.
Response: per-event accepted / duplicate / rejected outcomes.

The same models are imported by both Central (intake) and Station (transport),
which is what guarantees the two sides cannot silently drift apart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..enums import PaperType, RejectionCode, SyncEntityType, SyncOperation

CONTRACT_VERSION = "station-sync/v1"
MIN_BATCH = 1
MAX_BATCH = 500


class SyncEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    entity_type: SyncEntityType
    operation: SyncOperation = SyncOperation.UPSERT
    natural_key: dict[str, str]
    value: Any = None
    local_version: int
    actor_assignment_id: str
    occurred_at: datetime


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    station_code: str
    exam_id: str
    package_id: str
    package_version: int
    rules_version: str
    events: list[SyncEvent] = Field(min_length=MIN_BATCH, max_length=MAX_BATCH)
    station_time: datetime | None = Field(
        default=None,
        description=(
            "The station's own clock at the moment it sent this batch. Central "
            "subtracts it from its own time to measure that station's skew and "
            "normalises every occurred_at in the batch by it, so two writers can "
            "be ordered by when they typed rather than by when the network "
            "happened to deliver. Optional: a batch from an older station build "
            "simply carries no correction, which is why adding it keeps "
            "station-sync/v1."
        ),
    )


# ---------------------------------------------------------------------------
# Snapshot (Central -> station)
#
# The only downlink for entered data. Packages seed a station's *configuration*
# (schools, subjects, candidates, credentials) and deliberately carry no marks;
# without a snapshot a station has no way to see a correction made centrally, to
# see what a second station covering the same centre recorded, or to recover
# after being reinstalled — its reconcile digest can only report that the two
# sides disagree, never about what.
# ---------------------------------------------------------------------------


class SnapshotScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    centre_number: str
    subject_code: str
    paper_type: PaperType


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    station_code: str
    exam_id: str
    package_id: str
    station_time: datetime | None = Field(
        default=None,
        description="Station clock, for the same skew measurement as SyncRequest.",
    )
    scopes: list[SnapshotScopeRequest] = Field(
        default_factory=list,
        max_length=500,
        description=(
            "Restrict to these scopes. Empty means every scope in the station's "
            "package — convenient for a rebuilt station, and bounded because a "
            "station's scope is bounded."
        ),
    )


class SnapshotRow(BaseModel):
    """Central's authoritative state for one student's paper."""

    model_config = ConfigDict(extra="forbid")

    student_id: str
    is_present: bool
    #: None means no mark recorded — distinct from 0, which is a mark of zero.
    total: float | None = None
    #: Monotonic per paper, incremented on every accepted synced write. A station
    #: stores it so a later snapshot can be recognised as newer without consulting
    #: any clock.
    central_version: int = 0
    #: Who last wrote it: a station_code, or None when the value did not come
    #: through sync at all (a central correction, a bulk upload).
    written_by: str | None = None
    #: When that write was typed, on Central's clock (skew-corrected at the time
    #: it was applied). None when the value never came through sync.
    written_at: datetime | None = None


class SnapshotScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    centre_number: str
    subject_code: str
    paper_type: PaperType
    #: Computed with lazeims_common.reconcile so it is comparable, byte for byte,
    #: with the digest the station computes over the same scope.
    central_digest: str
    rows: list[SnapshotRow] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    exam_id: str
    scopes: list[SnapshotScope] = Field(default_factory=list)
    server_time: datetime
    #: Central's measurement of this station's clock error, positive when the
    #: station is behind. Returned so the station can show its operator that the
    #: machine's clock is wrong — the cause of conflicts that otherwise look
    #: arbitrary.
    clock_skew_seconds: float = 0.0
    truncated: bool = Field(
        default=False,
        description="True when scopes were dropped to stay within the response cap.",
    )


class AcceptedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    central_version: int


class DuplicateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str


class RejectedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    code: RejectionCode
    message: str


class SyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: list[AcceptedResult] = Field(default_factory=list)
    duplicates: list[DuplicateResult] = Field(default_factory=list)
    rejected: list[RejectedResult] = Field(default_factory=list)
    server_time: datetime
    exam_phase: str | None = Field(
        default=None,
        description=(
            "Central's current phase for this exam, so a station can warn its "
            "operator before entry locks instead of discovering it on the next "
            "rejected batch. Optional: a station talking to an older Central "
            "simply gets None, which is why adding it keeps station-sync/v1."
        ),
    )
