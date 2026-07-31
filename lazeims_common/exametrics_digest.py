"""Canonicalisation and digesting of the ExaMetrics collection payload (K3).

Central builds the collection payload out of SQL result sets, so its row order
is whatever the query planner produced; ExaMetrics rebuilds it out of its own
tables after ingest. If the two sides digested what they happened to hold, the
digests would disagree for data that is identical, and §7.2's digest-verified
``complete`` would reject good uploads.

So the canonical form is defined **here, once**, and both sides import it:

* rows are sorted by their natural key — ``schools`` by ``centre_number``,
  ``subjects`` by ``subject_code``, ``students`` by
  ``(centre_number, student_id)``, ``marks`` by
  ``(centre_number, student_id, subject_code)``;
* keys whose value is ``None`` are **dropped**, so an explicit
  ``"middle_name": null`` and an absent ``middle_name`` are the same row —
  Central emits the former and ExaMetrics stores the latter;
* everything else is delegated to :mod:`lazeims_common.hashing`, which already
  sorts object keys and emits compact UTF-8.

Ordering and null-dropping are therefore part of the **contract**, not an
implementation detail: changing either changes every digest.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .hashing import canonical_bytes, sha256_prefixed

#: Collection name -> the natural-key fields it is ordered by. The insertion
#: order of this mapping is also the order rows are drawn in when chunking, so
#: a chunked upload lands schools and subjects before the students and marks
#: that reference them.
COLLECTION_SORT_KEYS: Dict[str, tuple[str, ...]] = {
    "schools": ("centre_number",),
    "subjects": ("subject_code",),
    "students": ("centre_number", "student_id"),
    "marks": ("centre_number", "student_id", "subject_code"),
}

#: The collections a canonical payload is made of, in chunking order.
COLLECTION_NAMES: tuple[str, ...] = tuple(COLLECTION_SORT_KEYS)

#: Default rows per chunk, matching the published ``max_collection_chunk_size``.
DEFAULT_CHUNK_ROWS = 5000


def _drop_nulls(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Copy ``row`` without the keys whose value is ``None``."""
    return {key: value for key, value in row.items() if value is not None}


def _sort_key(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[str, ...]:
    """Total order over ``fields``, comparing as strings.

    Natural keys are strings on the wire (centre numbers and candidate numbers
    are zero-padded codes, not integers), and stringifying keeps a row with a
    missing key sortable instead of raising ``TypeError`` mid-digest.
    """
    return tuple("" if row.get(f) is None else str(row.get(f)) for f in fields)


def canonical_collection(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return ``payload`` in the canonical form both sides digest.

    Only the collections present in ``payload`` appear in the result: a payload
    without ``marks`` is a different payload from one with ``"marks": []``, and
    the digest says so. Any other top-level key is carried through untouched so
    an envelope field (a contract version, a closeout revision) is still part of
    what gets signed.
    """
    canonical: Dict[str, Any] = {}
    for name, fields in COLLECTION_SORT_KEYS.items():
        if name not in payload:
            continue
        rows = payload[name] or []
        canonical[name] = sorted(
            (_drop_nulls(row) for row in rows),
            key=lambda row: _sort_key(row, fields),
        )
    for key, value in payload.items():
        if key not in COLLECTION_SORT_KEYS:
            canonical[key] = value
    return canonical


def collection_digest(payload: Mapping[str, Any]) -> str:
    """``sha256:…`` digest of the canonical form of ``payload``.

    This is the value §7.2's ``complete`` verifies and the value Central quotes
    when it pushes a collection in one shot.
    """
    return sha256_prefixed(canonical_collection(payload))


def canonical_collection_bytes(payload: Mapping[str, Any]) -> bytes:
    """The exact bytes :func:`collection_digest` hashes.

    Exposed so a caller that needs to size or transmit the canonical payload
    does not have to re-derive it and risk drifting from the digest.
    """
    return canonical_bytes(canonical_collection(payload))


def chunk_payload(
    payload: Mapping[str, Any], max_rows: int = DEFAULT_CHUNK_ROWS
) -> List[Dict[str, Any]]:
    """Split ``payload`` into chunks of at most ``max_rows`` rows each (§7.2).

    Every chunk carries the same collection keys as the canonical payload, so
    concatenating the chunks in order reproduces it exactly and therefore
    reproduces its digest. Rows are drawn in :data:`COLLECTION_NAMES` order, so
    a chunk boundary never puts a mark ahead of the school it belongs to.

    A payload with no rows yields a single empty chunk rather than none: the
    server still has to be told the collection is empty.
    """
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    canonical = canonical_collection(payload)
    present = [name for name in COLLECTION_NAMES if name in canonical]
    extras = {k: v for k, v in canonical.items() if k not in COLLECTION_SORT_KEYS}

    def _empty_chunk() -> Dict[str, Any]:
        chunk: Dict[str, Any] = {name: [] for name in present}
        chunk.update(extras)
        return chunk

    chunks: List[Dict[str, Any]] = []
    current = _empty_chunk()
    used = 0
    for name in present:
        for row in canonical[name]:
            if used == max_rows:
                chunks.append(current)
                current = _empty_chunk()
                used = 0
            current[name].append(row)
            used += 1
    chunks.append(current)
    return chunks


def merge_chunks(chunks: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Reassemble chunks produced by :func:`chunk_payload` into one payload.

    Used by the server on ``complete`` and by the contract tests to prove that
    a chunked upload digests identically to a single-shot one.
    """
    merged: Dict[str, Any] = {}
    for chunk in chunks:
        for key, value in chunk.items():
            if key in COLLECTION_SORT_KEYS:
                merged.setdefault(key, []).extend(value or [])
            else:
                merged[key] = value
    return canonical_collection(merged)


def chunk_rows(chunk: Mapping[str, Any]) -> int:
    """Number of collection rows in one chunk."""
    return sum(len(chunk.get(name) or []) for name in COLLECTION_SORT_KEYS)


def chunk_manifest(chunks: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The manifest sent with §7.2's ``complete`` call.

    Carries a per-chunk digest as well as the whole-payload ``digest`` so a
    failed verification names the chunk that differs instead of only reporting
    that something does.
    """
    return {
        "chunk_count": len(chunks),
        "total_rows": sum(chunk_rows(chunk) for chunk in chunks),
        "digest": collection_digest(merge_chunks(chunks)),
        "chunks": [
            {
                "index": index,
                "rows": chunk_rows(chunk),
                "digest": sha256_prefixed(canonical_collection(chunk)),
            }
            for index, chunk in enumerate(chunks)
        ],
    }
