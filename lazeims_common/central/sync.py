"""Central-side ``station-sync/v1`` intake — the shared batch engine.

What this owns
--------------
The ordering and bookkeeping every Central must get identically right, because
the station's outbox depends on it:

1. dedupe by ``event_id``, distinguishing a harmless replay from the same id
   carrying a different payload;
2. isolate each event so one rejection cannot abort the batch;
3. write a receipt for accepted *and* rejected events;
4. return per-event outcomes.

Why per-event and not a count
-----------------------------
The station reconciles its outbox against ``accepted`` / ``duplicates`` /
``rejected`` by ``event_id``. An event named in none of the three is left PENDING
and retried, which is exactly how an interrupted sync resumes where it stopped.
A Central that answers with totals leaves the station unable to tell which of its
events landed, so it must either discard work or re-send forever.

Why the batch must not abort
----------------------------
A station carries hours of offline typing. Rejecting the whole batch because one
student was never registered would discard marks that have already been read off
the scripts once, and the scripts are at the marking centre.

What each Central supplies
--------------------------
Only the two seams that differ: how an event is *applied* to its own tables, and
where receipts are *stored*. Both are injected, which is also why this module
needs no database dependency and can be tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Protocol

from ..enums import EventStatus, RejectionCode
from ..hashing import sha256_prefixed

__all__ = [
    "SyncRejected",
    "ReceiptLike",
    "process_sync_batch",
    "payload_hash_of",
]


class SyncRejected(Exception):
    """One event cannot be applied. Carries a stable contract rejection code.

    Raised by a Central's ``apply_event`` and caught per event by
    :func:`process_sync_batch`, which turns it into a ``rejected`` entry and a
    receipt. Anything else propagating out of ``apply_event`` is a bug rather
    than a business rejection and is deliberately left to surface.
    """

    def __init__(self, code: RejectionCode | str, message: str, detail: Any = None):
        self.code = code.value if isinstance(code, RejectionCode) else str(code)
        self.message = message
        self.detail = detail
        super().__init__(message)


class ReceiptLike(Protocol):
    """The only thing the engine needs from a stored receipt."""

    payload_hash: str | None


@dataclass(frozen=True, slots=True)
class _Savepoint:
    commit: Callable[[], Awaitable[None]]
    rollback: Callable[[], Awaitable[None]]


def payload_hash_of(event: dict) -> str:
    """Canonical hash of an event's ``value``.

    Hashes ``value`` only, not the whole event: ``occurred_at`` and transport
    metadata legitimately differ between a first send and a retry, while a
    changed ``value`` under a reused ``event_id`` means the two sides disagree
    about what that event *was*.
    """
    return sha256_prefixed(event.get("value"))


async def process_sync_batch(
    events: list[dict],
    *,
    apply_event: Callable[[dict], Awaitable[None]],
    get_receipt: Callable[[str], Awaitable[ReceiptLike | None]],
    put_receipt: Callable[..., Awaitable[None]],
    savepoint: Callable[[], Awaitable[Any]],
    gate: Callable[[dict], Awaitable[tuple[str, str] | None]] | None = None,
) -> dict:
    """Process one batch and return the ``station-sync/v1`` response dict.

    Parameters
    ----------
    apply_event
        ``async (event) -> None``. Raise :class:`SyncRejected` to reject.
    get_receipt
        ``async (event_id) -> receipt | None`` for the dedupe check.
    put_receipt
        ``async (*, event_id, entity_type, status, payload_hash, rejection_code)``.
    savepoint
        ``async () -> obj`` exposing ``commit()`` / ``rollback()`` — SQLAlchemy's
        ``AsyncSession.begin_nested()`` satisfies this as-is.
    gate
        Optional ``async (event) -> (code, message) | None``, checked *after* the
        dedupe test and *before* applying. Used for whole-exam refusals such as a
        published exam or a locked phase.

        A gate refusal deliberately writes **no receipt**, unlike a
        :class:`SyncRejected` from ``apply_event``. The two are different in kind:
        a mark of 9999 will never become valid, but "the exam is published" stops
        being true the moment someone unpublishes it. Recording a receipt for a
        temporary refusal would mean the station's next attempt at that
        ``event_id`` came back as ``duplicate`` — the station would mark it
        accepted and never send it again, and the marks would be lost in silence.

        A gated event is still dedupe-checked first, so a station replaying a
        batch during a lock is told ``duplicate`` for what already landed rather
        than being handed a rejection that would overwrite its record of success.
    """
    accepted: list[dict] = []
    duplicates: list[dict] = []
    rejected: list[dict] = []

    for event in events:
        event_id = event.get("event_id") or ""
        entity_type = event.get("entity_type") or ""
        payload_hash = payload_hash_of(event)

        existing = await get_receipt(event_id)
        if existing is not None:
            existing_hash = getattr(existing, "payload_hash", None)
            if existing_hash and existing_hash != payload_hash:
                rejected.append({
                    "event_id": event_id,
                    "code": RejectionCode.EVENT_ID_PAYLOAD_CONFLICT.value,
                    "message": "Event id already used with a different payload.",
                })
            else:
                duplicates.append({"event_id": event_id})
            continue

        if gate is not None:
            refusal = await gate(event)
            if refusal is not None:
                code, message = refusal
                # No receipt: see the `gate` note above.
                rejected.append({"event_id": event_id, "code": code, "message": message})
                continue

        sp = await savepoint()
        try:
            await apply_event(event)
            await put_receipt(
                event_id=event_id,
                entity_type=entity_type,
                status=EventStatus.ACCEPTED.value,
                payload_hash=payload_hash,
                rejection_code=None,
            )
            await sp.commit()
            accepted.append({
                "event_id": event_id,
                "central_version": int(event.get("local_version") or 1),
            })
        except SyncRejected as exc:
            # Roll back only this event's writes, then record the rejection
            # OUTSIDE the savepoint — a receipt written inside it would be
            # discarded by the same rollback, and the station would be told to
            # retry an event this Central has already judged.
            await sp.rollback()
            await put_receipt(
                event_id=event_id,
                entity_type=entity_type,
                status=EventStatus.REJECTED.value,
                payload_hash=payload_hash,
                rejection_code=exc.code,
            )
            rejected.append({
                "event_id": event_id,
                "code": exc.code,
                "message": exc.message,
            })

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
