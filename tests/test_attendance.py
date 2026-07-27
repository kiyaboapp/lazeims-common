from __future__ import annotations

import pytest

from lazeims_common.enums import PaperType
from lazeims_common.validation.attendance import (
    AttendanceRow,
    effective_attendance,
    has_specific_transcription,
)


def test_specific_paper_wins_over_all_baseline():
    rows = [
        AttendanceRow(PaperType.ALL, is_present=True),
        AttendanceRow(PaperType.THEORY1, is_present=False),
    ]
    assert effective_attendance(rows, PaperType.THEORY1) is False


def test_falls_back_to_all_baseline():
    rows = [AttendanceRow(PaperType.ALL, is_present=False)]
    assert effective_attendance(rows, PaperType.THEORY1) is False


def test_defaults_present_when_no_rows():
    assert effective_attendance([], PaperType.THEORY1) is True


def test_default_present_override():
    assert effective_attendance([], PaperType.THEORY1, default_present=False) is False


def test_all_paper_type_rejected():
    with pytest.raises(ValueError):
        effective_attendance([], PaperType.ALL)


def test_has_specific_transcription():
    rows = [AttendanceRow(PaperType.ALL, is_present=True)]
    assert has_specific_transcription(rows, PaperType.THEORY1) is False
    rows.append(AttendanceRow(PaperType.THEORY1, is_present=True))
    assert has_specific_transcription(rows, PaperType.THEORY1) is True
