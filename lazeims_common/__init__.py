"""lazeims_common — shared validation rules and versioned contracts.

Imported by both ``lazeims-central-api`` and ``lazeims-station`` so every
collection rule lives exactly once.
"""

from __future__ import annotations

from . import (
    enums,
    errors,
    exametrics_digest,
    hashing,
    natural_keys,
    portable,
    reconcile,
    schemas,
    signing,
    validation,
)
from .errors import LazeimsError, ValidationError, error_envelope
from .exametrics_digest import (
    canonical_collection,
    chunk_manifest,
    chunk_payload,
    collection_digest,
    merge_chunks,
)

__version__ = "0.1.0"

# Frozen contract identifiers (Milestone 0).
RULES_VERSION = "1.0"
STATION_PACKAGE_CONTRACT = "station-package/v1"
STATION_SYNC_CONTRACT = "station-sync/v1"
COLLECTION_EXPORT_CONTRACT = "collection-export/v1"
EXAMETRICS_INTEGRATION_CONTRACT = "exametrics-integration/v2"

__all__ = [
    "enums",
    "errors",
    "exametrics_digest",
    "hashing",
    "natural_keys",
    "portable",
    "reconcile",
    "schemas",
    "signing",
    "validation",
    "LazeimsError",
    "ValidationError",
    "error_envelope",
    "canonical_collection",
    "collection_digest",
    "chunk_payload",
    "chunk_manifest",
    "merge_chunks",
    "__version__",
    "RULES_VERSION",
    "STATION_PACKAGE_CONTRACT",
    "STATION_SYNC_CONTRACT",
    "COLLECTION_EXPORT_CONTRACT",
    "EXAMETRICS_INTEGRATION_CONTRACT",
]
