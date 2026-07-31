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

from ..enums import RejectionCode, SyncEntityType, SyncOperation

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
