"""Versioned Pydantic contracts shared by Central and Station."""

from __future__ import annotations

from .attendance import AttendanceIn
from .collection_export import (
    CollectionManifest,
    CollectionSnapshot,
    ScopeCount,
)
from .exametrics import (
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
from .marks import ItemMarkIn, StudentPaperMarksIn, TotalMarkIn
from .station_package import (
    PackageScope,
    StationPackageManifest,
)
from .station_sync import (
    AcceptedResult,
    DuplicateResult,
    RejectedResult,
    SyncEvent,
    SyncRequest,
    SyncResponse,
)

__all__ = [
    "AttendanceIn",
    "ItemMarkIn",
    "TotalMarkIn",
    "StudentPaperMarksIn",
    "StationPackageManifest",
    "PackageScope",
    "SyncEvent",
    "SyncRequest",
    "SyncResponse",
    "AcceptedResult",
    "DuplicateResult",
    "RejectedResult",
    "CollectionManifest",
    "CollectionSnapshot",
    "ScopeCount",
    "CapabilitiesResponse",
    "ExamProvisionRequest",
    "ExamProvisionResponse",
    "KeyProvisionRequest",
    "KeyProvisionResponse",
    "ProcessingQuoteOut",
    "ProcessingRequestIn",
    "RequesterInfo",
    "SubjectSpec",
    "TenantExamInfo",
    "TenantInfo",
]
