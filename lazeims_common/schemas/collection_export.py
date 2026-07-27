"""Versioned collection export/snapshot contract (``collection-export/v1``).

A sealed collection snapshot is service-neutral: it carries collected data +
configuration + integrity metadata only. It must never reference processing
algorithms, rankings, analyses, or any external processor's internals.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "collection-export/v1"


class ScopeCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school_code: str
    subject_code: str
    paper_type: str
    present_count: int
    absent_count: int
    marks_count: int
    scope_hash: str


class CollectionManifest(BaseModel):
    """The canonical, hashable manifest of a sealed collection."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default=CONTRACT_VERSION)
    exam_id: str
    configuration_version: int
    configuration_hash: str
    closeout_revision: int
    sealed_at: datetime
    scope_counts: list[ScopeCount] = Field(default_factory=list)
    total_students: int
    total_marks: int


class CollectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    exam_id: str
    closeout_revision: int
    configuration_hash: str
    manifest: CollectionManifest
    content_hash: str
    sealed_by: str
    sealed_at: datetime
