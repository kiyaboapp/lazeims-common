"""Attendance rules.

The system never originates attendance — it transcribes a paper report (ISAL,
per room; or the Supervisor's CAL rolled up per subject). This module defines
the single ``effective attendance`` resolver used everywhere, plus the gate that
marks entry depends on.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import PaperType


@dataclass(frozen=True, slots=True)
class AttendanceRow:
    """A stored attendance transcription for one student-subject + paper.

    ``paper_type`` is either a real paper (a Data Enterer's own ISAL
    transcription) or ``ALL`` (Chief IT's optional subject-wide CAL baseline).
    """

    paper_type: PaperType
    is_present: bool


def effective_attendance(
    rows: list[AttendanceRow],
    paper_type: PaperType,
    *,
    default_present: bool = True,
) -> bool:
    """Resolve whether a student is present for ``paper_type``.

    Lookup order (Guide §2.3, must be implemented exactly once — here):
        (a) a row with the specific ``paper_type`` (a Data Enterer's own
            transcription) always wins;
        (b) else a row with ``paper_type = ALL`` (Chief IT's CAL baseline);
        (c) else ``default_present`` (a UI starting value only — NOT stored
            evidence; callers must persist a real transcription before marks).

    ``paper_type`` must be a real paper, never ``ALL``.
    """
    if paper_type == PaperType.ALL:
        raise ValueError("effective_attendance requires a real paper, not ALL")

    specific = next((r for r in rows if r.paper_type == paper_type), None)
    if specific is not None:
        return specific.is_present

    baseline = next((r for r in rows if r.paper_type == PaperType.ALL), None)
    if baseline is not None:
        return baseline.is_present

    return default_present


def has_specific_transcription(
    rows: list[AttendanceRow], paper_type: PaperType
) -> bool:
    """True if a paper-specific attendance row exists (the mandatory pre-marks
    step). Marks entry is gated on this being true."""
    return any(r.paper_type == paper_type for r in rows)
