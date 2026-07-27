"""Deterministic scope reconciliation digest.

Central and Station independently build the SAME normalized record list for a
finalized scope and hash it with the canonical hasher. If the digests match, the
scope reconciles (``MATCHED``). Because the record schema and the canonical JSON
are defined here once, both sides always agree byte-for-byte.

Canonical scope record schema (one dict per student-paper that has data):
    {
      "student_id": str,
      "present": bool,
      "mode": "TOTAL_MARKS" | "ITEM_LEVEL",
      "total": str | None,                 # present in TOTAL_MARKS
      "items": {question_number: str},     # present in ITEM_LEVEL (sorted by key in canonical form)
    }
Records are sorted by ``student_id`` before hashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .hashing import sha256_prefixed


def _numstr(value) -> str:
    """Canonical numeric string so 67, 67.0, 67.00, Decimal('67') all match."""
    return format(Decimal(str(value)).normalize(), "f")


def normalize_total_record(student_id: str, present: bool, total) -> dict:
    return {
        "student_id": student_id,
        "present": bool(present),
        "mode": "TOTAL_MARKS",
        "total": None if total is None else _numstr(total),
    }


def normalize_item_record(student_id: str, present: bool, items: dict[str, object]) -> dict:
    return {
        "student_id": student_id,
        "present": bool(present),
        "mode": "ITEM_LEVEL",
        "items": {str(k): _numstr(v) for k, v in items.items()},
    }


def scope_digest(records: list[dict]) -> str:
    """Return the canonical SHA-256 digest for a scope's records.

    Records are sorted by ``student_id`` so ordering never affects the result.
    """
    ordered = sorted(records, key=lambda r: r["student_id"])
    return sha256_prefixed(ordered)


@dataclass(frozen=True, slots=True)
class ScopeCounts:
    present: int
    absent: int
    with_marks: int

    def as_dict(self) -> dict:
        return {"present": self.present, "absent": self.absent, "with_marks": self.with_marks}


def counts_from_records(records: list[dict]) -> ScopeCounts:
    present = sum(1 for r in records if r["present"])
    absent = sum(1 for r in records if not r["present"])
    with_marks = sum(
        1 for r in records
        if (r.get("total") is not None) or (r.get("items"))
    )
    return ScopeCounts(present=present, absent=absent, with_marks=with_marks)


def reconcile(local_digest: str, central_digest: str) -> str:
    """Return ``MATCHED`` or ``MISMATCHED``."""
    return "MATCHED" if local_digest == central_digest else "MISMATCHED"
