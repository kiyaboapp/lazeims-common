"""Marks rules — the heart of the system.

THE one rule that matters most: **no blank marks, ever.** A present student must
have an explicit value for every required field (0 is valid, blank/None is not).
An absent student may have no marks at all.

These functions validate a single student-paper submission (one total, or a
complete item set). Central and Station both call them; each adds its own scope,
writer-assignment and finalize checks around the result.
"""

from __future__ import annotations

from decimal import Decimal

from ..enums import FillingMode, PaperType, RejectionCode
from ..errors import ValidationError
from .config import PaperConfig, as_decimal
from .scoring import compute_paper_total


def _check_range(qnum_or_label: str, value: Decimal, max_marks: Decimal) -> None:
    if value < 0:
        raise ValidationError(
            RejectionCode.MARK_OUT_OF_RANGE,
            f"Mark for {qnum_or_label} is negative ({value}).",
            {"field": qnum_or_label, "value": str(value)},
        )
    if value > max_marks:
        raise ValidationError(
            RejectionCode.MARK_OUT_OF_RANGE,
            f"Mark for {qnum_or_label} ({value}) exceeds the maximum ({max_marks}).",
            {"field": qnum_or_label, "value": str(value), "max": str(max_marks)},
        )


def _coerce_present_value(field: str, raw) -> Decimal:
    """A present student's field must be an explicit, non-null number.

    ``None`` (or missing, passed as ``None``) is a blank and always rejected.
    """
    if raw is None:
        raise ValidationError(
            RejectionCode.BLANK_MARK_NOT_ALLOWED,
            f"Field {field} is blank; a present student needs an explicit value (0 is valid).",
            {"field": field},
        )
    try:
        return as_decimal(raw)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValidationError(
            RejectionCode.BLANK_MARK_NOT_ALLOWED,
            f"Field {field} has a non-numeric value; an explicit number is required.",
            {"field": field, "value": repr(raw)},
        ) from exc


def validate_total_mark(
    *,
    is_present: bool,
    paper: PaperConfig,
    total_marks_obtained,
) -> Decimal | None:
    """Validate a Mode A (total-marks) submission for one student-paper.

    Returns the validated total as ``Decimal`` for a present student, or
    ``None`` for an absent student (who must have no mark).
    """
    if paper.paper_type == PaperType.ALL:
        raise ValidationError(
            RejectionCode.MARK_OUT_OF_RANGE,
            "Marks cannot be recorded against the ALL attendance baseline.",
            {"paper_type": "ALL"},
        )

    if not is_present:
        if total_marks_obtained is not None:
            raise ValidationError(
                RejectionCode.ABSENT_STUDENT_HAS_MARKS,
                "An absent student must not have any marks.",
                {"paper_type": paper.paper_type.value},
            )
        return None

    value = _coerce_present_value("total", total_marks_obtained)
    _check_range("total", value, paper.paper_max)
    return value


def validate_item_marks(
    *,
    is_present: bool,
    paper: PaperConfig,
    item_marks: dict[str, object] | None,
) -> Decimal | None:
    """Validate a Mode B (item-level) submission for one student-paper.

    * Absent student: must have no items at all -> returns ``None``.
    * Present student: every configured question must have an explicit,
      in-range value (no blanks, no missing, no extras). Returns the computed
      paper total (best-N-of-M), also range-checked against the paper max.
    """
    if paper.paper_type == PaperType.ALL:
        raise ValidationError(
            RejectionCode.MARK_OUT_OF_RANGE,
            "Marks cannot be recorded against the ALL attendance baseline.",
            {"paper_type": "ALL"},
        )

    item_marks = item_marks or {}

    if not is_present:
        if item_marks:
            raise ValidationError(
                RejectionCode.ABSENT_STUDENT_HAS_MARKS,
                "An absent student must not have any marks.",
                {"paper_type": paper.paper_type.value},
            )
        return None

    qmap = paper.question_map()
    required = set(qmap)
    provided = set(item_marks)

    missing = sorted(required - provided)
    if missing:
        raise ValidationError(
            RejectionCode.BLANK_MARK_NOT_ALLOWED,
            f"Missing marks for question(s): {', '.join(missing)}. Every configured question needs an explicit value.",
            {"missing": missing},
        )

    extra = sorted(provided - required)
    if extra:
        raise ValidationError(
            RejectionCode.INCOMPLETE_QUESTION_SET,
            f"Marks supplied for unconfigured question(s): {', '.join(extra)}.",
            {"extra": extra},
        )

    validated: dict[str, Decimal] = {}
    for qnum, q in qmap.items():
        value = _coerce_present_value(qnum, item_marks[qnum])
        _check_range(qnum, value, as_decimal(q.max_marks))
        validated[qnum] = value

    total = compute_paper_total(paper, validated)
    if total > as_decimal(paper.paper_max):
        raise ValidationError(
            RejectionCode.MARK_OUT_OF_RANGE,
            f"Computed paper total {total} exceeds the paper maximum {paper.paper_max}.",
            {"total": str(total), "max": str(paper.paper_max)},
        )
    return total


def validate_marks_submission(
    *,
    mode: FillingMode,
    is_present: bool,
    has_attendance_transcription: bool,
    paper: PaperConfig,
    total_marks_obtained=None,
    item_marks: dict[str, object] | None = None,
) -> Decimal | None:
    """Full gate for one student-paper marks submission.

    Enforces, in order:
      1. Attendance must have been transcribed for this paper first
         (``ATTENDANCE_REQUIRED_FIRST``).
      2. Mode-specific no-blank / range / completeness / absent rules.

    Returns the validated/computed paper total (or ``None`` if absent).
    """
    if not has_attendance_transcription:
        raise ValidationError(
            RejectionCode.ATTENDANCE_REQUIRED_FIRST,
            "Attendance must be transcribed for this paper before marks can be entered.",
            {"paper_type": paper.paper_type.value},
        )

    if mode == FillingMode.TOTAL_MARKS:
        return validate_total_mark(
            is_present=is_present,
            paper=paper,
            total_marks_obtained=total_marks_obtained,
        )
    if mode == FillingMode.ITEM_LEVEL:
        return validate_item_marks(
            is_present=is_present,
            paper=paper,
            item_marks=item_marks,
        )
    raise ValidationError(
        RejectionCode.CONFIGURATION_MISMATCH,
        f"Unknown filling mode {mode!r}.",
        {"mode": str(mode)},
    )
