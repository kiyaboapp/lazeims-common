"""Versioned Pydantic input contract for attendance transcription."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..enums import AttendanceSource, PaperType


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class AttendanceIn(_Strict):
    """A transcription of a paper attendance report for one student-subject.

    ``paper_type = ALL`` is used only for the optional subject-wide CAL
    baseline (source ``SUPERVISOR_CAL_TRANSCRIPTION``).
    """

    student_id: str
    subject_code: str
    paper_type: PaperType
    is_present: bool
    source: AttendanceSource
