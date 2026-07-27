"""Deterministic canonical JSON + SHA-256 hashing.

Used for:
    * reconciliation (station and Central independently hash a scope's data and
      compare — the hashes must match byte-for-byte);
    * sync event payload-hashing (dedupe + tamper detection);
    * sealed collection snapshots (immutable, reproducible integrity).

The canonical form must be identical on both sides, so it is defined here once:
    * object keys sorted lexicographically;
    * no insignificant whitespace;
    * UTF-8, with non-ASCII preserved (``ensure_ascii=False``);
    * numbers emitted via Python's ``json`` (integers stay integers; floats are
      normalised — callers should pass marks as ints or Decimal-as-string to
      avoid float ambiguity).
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # Represent decimals as their shortest exact string to keep hashing
        # deterministic and free of binary-float artefacts.
        return format(obj.normalize(), "f")
    if hasattr(obj, "value") and hasattr(obj, "name"):  # Enum-like
        return obj.value
    raise TypeError(f"Type {type(obj).__name__} is not canonical-JSON serialisable")


def canonical_json(data: Any) -> str:
    """Return the deterministic canonical JSON string for ``data``."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    )


def canonical_bytes(data: Any) -> bytes:
    """Canonical JSON encoded as UTF-8 bytes."""
    return canonical_json(data).encode("utf-8")


def sha256_hex(data: Any) -> str:
    """SHA-256 hex digest of the canonical JSON of ``data``."""
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def sha256_prefixed(data: Any) -> str:
    """SHA-256 digest prefixed with ``sha256:`` (contract format for hashes)."""
    return f"sha256:{sha256_hex(data)}"


def hash_payload(data: Any) -> str:
    """Alias used by the sync layer for event payload hashing."""
    return sha256_prefixed(data)
