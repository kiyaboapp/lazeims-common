"""Write-conflict resolution for ``station-sync/v1``, defined once for both Centrals.

The problem this exists to solve
-------------------------------
A paper's mark has more than one possible author. A Data Enterer types it at a
marking centre with no internet; a second station may legitimately hold the same
centre (a LOCATION station overlapping a SCHOOLS one); and a person with the
right role can correct the same value in the Central UI. Nothing about the
transport orders those writers: an event reaches Central when the network
returns, which may be hours after it was typed and long after a correction was
made centrally.

Applying whatever arrives last — which is what a bare ``setattr`` in an
``apply_event`` does — makes the *network* the arbiter. The observable failure is
a correction that disappears: a mark fixed centrally at 14:00 is silently
replaced at 15:00 by the 09:00 value a station had been holding offline all day,
and nothing in the response says so.

Why the decision is time-based, and why time needs normalising first
--------------------------------------------------------------------
The rule that matches the domain is *the later authorship wins*: whoever most
recently looked at the script and typed a number is the one to believe. That
needs comparable timestamps, and a station's clock is exactly the clock nobody
can trust — the machines are offline by design, so no NTP, and a dead CMOS
battery puts a marking centre in 2019.

So each side's clock is measured rather than assumed. The station sends its own
current time with every batch; Central subtracts it from its own to get that
station's skew, and normalises every ``occurred_at`` in the batch by it. What is
compared is therefore not two raw clocks but two intervals-before-now, which is
the same quantity on both machines.

Ordering *within* one station does not need clocks at all: ``local_version`` is a
per-station monotonic counter, so it settles retries and out-of-order delivery
exactly, and it is preferred whenever both writes came from the same station.

Deliberately pure
-----------------
No database, no clock of its own, no I/O — every input is passed in. That is what
lets both Centrals reach the same verdict from different schemas, and what makes
each rule testable as a table of cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

__all__ = [
    "Resolution",
    "StoredWrite",
    "IncomingWrite",
    "clock_skew_seconds",
    "normalize_occurred_at",
    "decide",
    "ConflictDecision",
]


class Resolution(str, Enum):
    """What a Central should do with an incoming write."""

    #: Write it. The incoming event is the most recent authorship of this value.
    APPLY = "APPLY"
    #: Accept without writing: the stored value is already exactly this.
    NO_OP = "NO_OP"
    #: Refuse it. Something newer is already stored, so writing would undo work.
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class StoredWrite:
    """What a Central already recorded for one natural key + paper.

    ``value_hash`` is the hash of the value *this* mechanism last wrote. Compared
    against the row's current value it answers a question no timestamp can: has
    anything outside sync touched this paper since? A row's ``updated_at`` cannot,
    because results processing and rank computation bump it too.
    """

    station_code: str | None
    local_version: int
    occurred_at: datetime
    value_hash: str | None = None


@dataclass(frozen=True, slots=True)
class IncomingWrite:
    station_code: str
    local_version: int
    occurred_at: datetime
    value_hash: str


@dataclass(frozen=True, slots=True)
class ConflictDecision:
    resolution: Resolution
    #: Operator-facing sentence. Reaches a Data Enterer on a rejection, so it says
    #: what happened and what to do, never "conflict".
    reason: str
    #: True when applying replaces a value that arrived from outside sync — a
    #: central correction, an import. Worth auditing rather than blocking: the
    #: station operator is the one holding the script.
    overwrites_foreign_change: bool = False


def clock_skew_seconds(station_time: datetime | None, server_time: datetime) -> float:
    """How far a station's clock is behind this Central's, in seconds.

    Positive means the station is behind. ``None`` station time (an older station
    build that does not send one) yields ``0.0``: no correction, which degrades to
    comparing raw clocks rather than refusing to decide.
    """
    if station_time is None:
        return 0.0
    return (_aware(server_time) - _aware(station_time)).total_seconds()


def normalize_occurred_at(occurred_at: datetime, *, skew_seconds: float) -> datetime:
    """Restate a station-clock timestamp on Central's clock.

    The correction is the skew measured for the batch it arrived in, so it is
    exact for events typed under that same wrong clock — which is the normal case,
    since an offline machine's clock does not change on its own. An operator who
    fixes the clock mid-session makes earlier events under-corrected; the raw
    value and the skew are both stored so that stays recoverable instead of
    becoming an unexplained ordering.
    """
    return _aware(occurred_at) + timedelta(seconds=skew_seconds)


def decide(
    incoming: IncomingWrite,
    stored: StoredWrite | None,
    *,
    current_value_hash: str | None = None,
) -> ConflictDecision:
    """Resolve one incoming write against what is already stored.

    ``current_value_hash`` is the hash of the value the row holds *right now*.
    When it differs from ``stored.value_hash``, something outside sync wrote it.

    Both timestamps must already be normalised (see :func:`normalize_occurred_at`);
    this function does no clock correction of its own, so a caller cannot
    accidentally compare one corrected time against one raw one.
    """
    if stored is None:
        # Nothing has been synced for this paper. If the row nevertheless holds a
        # value, it came from somewhere else — an upload, a central edit — and the
        # station's fresh transcription supersedes it, visibly.
        foreign = current_value_hash is not None and current_value_hash != incoming.value_hash
        return ConflictDecision(
            Resolution.APPLY,
            "First synced write for this paper.",
            overwrites_foreign_change=foreign,
        )

    same_station = (
        stored.station_code is not None
        and stored.station_code == incoming.station_code
    )

    foreign_change = (
        stored.value_hash is not None
        and current_value_hash is not None
        and current_value_hash != stored.value_hash
    )

    if same_station:
        # One station, one monotonic counter: no clock is involved, so a retry
        # that overtakes its successor cannot resurrect an older mark.
        if incoming.local_version > stored.local_version:
            return ConflictDecision(
                Resolution.APPLY,
                "Newer entry from the same station.",
                overwrites_foreign_change=foreign_change,
            )
        if (
            incoming.local_version == stored.local_version
            and incoming.value_hash == stored.value_hash
        ):
            return ConflictDecision(
                Resolution.NO_OP,
                "Already recorded with the same value.",
            )
        return ConflictDecision(
            Resolution.STALE,
            (
                f"A later entry for this paper (version {stored.local_version}) is "
                f"already recorded; this one is version {incoming.local_version}. "
                "Nothing was changed — the value on the server is the newer one."
            ),
        )

    # Two different writers. Now the clocks matter, and they have been normalised
    # onto Central's, so this compares when each was typed, not when it arrived.
    if incoming.occurred_at > stored.occurred_at:
        return ConflictDecision(
            Resolution.APPLY,
            (
                f"Typed after the value recorded by "
                f"{stored.station_code or 'another writer'}."
            ),
            overwrites_foreign_change=foreign_change,
        )

    if incoming.occurred_at < stored.occurred_at:
        return ConflictDecision(
            Resolution.STALE,
            (
                f"{stored.station_code or 'Another writer'} recorded this paper "
                "later than this entry was typed. Nothing was changed. If this "
                "entry is the correct one, re-enter it so it carries a current "
                "time."
            ),
        )

    if incoming.value_hash == stored.value_hash:
        return ConflictDecision(
            Resolution.NO_OP,
            "Another writer recorded the same value at the same moment.",
        )

    # Same instant, different values, different writers. Keeping what is stored is
    # the only deterministic answer available — and it is the arrival order, which
    # at least one operator has already been told succeeded.
    return ConflictDecision(
        Resolution.STALE,
        (
            f"{stored.station_code or 'Another writer'} recorded a different value "
            "for this paper at the same moment. Nothing was changed — check with "
            "the exam administrator which is correct."
        ),
    )


def _aware(value: datetime) -> datetime:
    """Treat a naive datetime as UTC.

    Naive values reach here from JSON that omitted an offset. Assuming UTC is the
    contract's own convention; the alternative — raising — would reject a whole
    batch over a formatting detail.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
