from __future__ import annotations

from decimal import Decimal

import pytest

from lazeims_common.enums import FillingMode, PaperType, RejectionCode
from lazeims_common.errors import ValidationError
from lazeims_common.validation.marks import (
    validate_item_marks,
    validate_marks_submission,
    validate_total_mark,
)


# ---- Mode A: total ----

def test_total_present_ok(total_paper):
    assert validate_total_mark(is_present=True, paper=total_paper, total_marks_obtained=67) == Decimal("67")


def test_total_zero_is_valid(total_paper):
    assert validate_total_mark(is_present=True, paper=total_paper, total_marks_obtained=0) == Decimal("0")


def test_total_blank_rejected(total_paper):
    with pytest.raises(ValidationError) as exc:
        validate_total_mark(is_present=True, paper=total_paper, total_marks_obtained=None)
    assert exc.value.code == RejectionCode.BLANK_MARK_NOT_ALLOWED


def test_total_absent_with_marks_rejected(total_paper):
    with pytest.raises(ValidationError) as exc:
        validate_total_mark(is_present=False, paper=total_paper, total_marks_obtained=10)
    assert exc.value.code == RejectionCode.ABSENT_STUDENT_HAS_MARKS


def test_total_absent_no_marks_ok(total_paper):
    assert validate_total_mark(is_present=False, paper=total_paper, total_marks_obtained=None) is None


def test_total_over_max_rejected(total_paper):
    with pytest.raises(ValidationError) as exc:
        validate_total_mark(is_present=True, paper=total_paper, total_marks_obtained=101)
    assert exc.value.code == RejectionCode.MARK_OUT_OF_RANGE


def test_total_negative_rejected(total_paper):
    with pytest.raises(ValidationError) as exc:
        validate_total_mark(is_present=True, paper=total_paper, total_marks_obtained=-1)
    assert exc.value.code == RejectionCode.MARK_OUT_OF_RANGE


# ---- Mode B: items ----

def _full_items():
    return {
        "1": 10, "2": 8, "3": 6,
        "4": 20, "5": 15, "6": 12, "7": 0, "8": 0,
    }


def test_items_present_ok(item_paper):
    total = validate_item_marks(is_present=True, paper=item_paper, item_marks=_full_items())
    assert total == Decimal("71")


def test_items_missing_question_rejected(item_paper):
    items = _full_items()
    del items["5"]
    with pytest.raises(ValidationError) as exc:
        validate_item_marks(is_present=True, paper=item_paper, item_marks=items)
    assert exc.value.code == RejectionCode.BLANK_MARK_NOT_ALLOWED
    assert "5" in exc.value.details["missing"]


def test_items_blank_value_rejected(item_paper):
    items = _full_items()
    items["5"] = None
    with pytest.raises(ValidationError) as exc:
        validate_item_marks(is_present=True, paper=item_paper, item_marks=items)
    assert exc.value.code == RejectionCode.BLANK_MARK_NOT_ALLOWED


def test_items_extra_question_rejected(item_paper):
    items = _full_items()
    items["99"] = 5
    with pytest.raises(ValidationError) as exc:
        validate_item_marks(is_present=True, paper=item_paper, item_marks=items)
    assert exc.value.code == RejectionCode.INCOMPLETE_QUESTION_SET


def test_items_out_of_range_rejected(item_paper):
    items = _full_items()
    items["1"] = 11  # max is 10
    with pytest.raises(ValidationError) as exc:
        validate_item_marks(is_present=True, paper=item_paper, item_marks=items)
    assert exc.value.code == RejectionCode.MARK_OUT_OF_RANGE


def test_items_absent_with_marks_rejected(item_paper):
    with pytest.raises(ValidationError) as exc:
        validate_item_marks(is_present=False, paper=item_paper, item_marks={"1": 5})
    assert exc.value.code == RejectionCode.ABSENT_STUDENT_HAS_MARKS


def test_items_absent_no_marks_ok(item_paper):
    assert validate_item_marks(is_present=False, paper=item_paper, item_marks={}) is None


def test_items_all_zero_present_ok(item_paper):
    items = {k: 0 for k in _full_items()}
    assert validate_item_marks(is_present=True, paper=item_paper, item_marks=items) == Decimal("0")


# ---- full gate ----

def test_gate_requires_attendance_first(item_paper):
    with pytest.raises(ValidationError) as exc:
        validate_marks_submission(
            mode=FillingMode.ITEM_LEVEL,
            is_present=True,
            has_attendance_transcription=False,
            paper=item_paper,
            item_marks=_full_items(),
        )
    assert exc.value.code == RejectionCode.ATTENDANCE_REQUIRED_FIRST


def test_gate_total_mode_ok(total_paper):
    total = validate_marks_submission(
        mode=FillingMode.TOTAL_MARKS,
        is_present=True,
        has_attendance_transcription=True,
        paper=total_paper,
        total_marks_obtained=55,
    )
    assert total == Decimal("55")


def test_gate_item_mode_ok(item_paper):
    total = validate_marks_submission(
        mode=FillingMode.ITEM_LEVEL,
        is_present=True,
        has_attendance_transcription=True,
        paper=item_paper,
        item_marks=_full_items(),
    )
    assert total == Decimal("71")


def test_marks_against_all_baseline_rejected():
    from lazeims_common.validation.config import PaperConfig
    paper = PaperConfig(PaperType.ALL, Decimal("100"))
    with pytest.raises(ValidationError) as exc:
        validate_total_mark(is_present=True, paper=paper, total_marks_obtained=10)
    assert exc.value.code == RejectionCode.MARK_OUT_OF_RANGE
