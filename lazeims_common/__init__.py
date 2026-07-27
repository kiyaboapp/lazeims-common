"""lazeims_common — shared validation rules and versioned contracts.

Imported by both ``lazeims-central-api`` and ``lazeims-station`` so every
collection rule lives exactly once.
"""

from __future__ import annotations

from . import enums, errors, hashing, natural_keys, portable, reconcile, schemas, validation
from .errors import LazeimsError, ValidationError, error_envelope

__version__ = "0.1.0"

# Frozen contract identifiers (Milestone 0).
RULES_VERSION = "1.0"
STATION_PACKAGE_CONTRACT = "station-package/v1"
STATION_SYNC_CONTRACT = "station-sync/v1"
COLLECTION_EXPORT_CONTRACT = "collection-export/v1"

__all__ = [
    "enums",
    "errors",
    "hashing",
    "natural_keys",
    "portable",
    "reconcile",
    "schemas",
    "validation",
    "LazeimsError",
    "ValidationError",
    "error_envelope",
    "__version__",
    "RULES_VERSION",
    "STATION_PACKAGE_CONTRACT",
    "STATION_SYNC_CONTRACT",
    "COLLECTION_EXPORT_CONTRACT",
]
