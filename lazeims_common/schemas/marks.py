"""Versioned Pydantic input contracts for marks."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..enums import FillingMode, PaperType


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ItemMarkIn(_Strict):
    """One question's mark. ``marks`` is required and never null (no blanks)."""

    question_number: str
    marks: Decimal = Field(ge=0)


class TotalMarkIn(_Strict):
    """A Mode A single-total submission for one student-paper."""

    student_id: str
    subject_code: str
    paper_type: PaperType
    total_marks_obtained: Decimal | None = Field(default=None, ge=0)


class StudentPaperMarksIn(_Strict):
    """One atomic student-paper submission — the whole required set at once.

    Mirrors the ``STUDENT_PAPER_MARKS_REPLACED`` sync event so a partial or
    invalid intermediate record can never be created. For an absent student,
    ``total_marks_obtained`` is null and ``items`` is empty/None.
    """

    student_id: str
    subject_code: str
    paper_type: PaperType
    mode: FillingMode
    attendance_revision: int | None = None
    total_marks_obtained: Decimal | None = Field(default=None, ge=0)
    items: list[ItemMarkIn] | None = None

    def item_map(self) -> dict[str, Decimal]:
        return {i.question_number: i.marks for i in (self.items or [])}
