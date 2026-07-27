from __future__ import annotations

import pytest

from lazeims_common.enums import PaperType, RejectionCode
from lazeims_common.errors import ValidationError
from lazeims_common.natural_keys import (
    NaturalKey,
    build_natural_key,
    parse_natural_key,
    prefer_hyphen_separator,
    validate_student_id,
)


@pytest.mark.parametrize("sid", ["S1234-0123", "S1234/0123", "PS0001", "A07-99-1"])
def test_valid_student_ids_unchanged(sid):
    assert validate_student_id(sid) == sid


@pytest.mark.parametrize("sid", ["", " S1", "S1 ", "S 1", "S@1", "S--", "-S1"])
def test_invalid_student_ids_rejected(sid):
    with pytest.raises(ValidationError) as exc:
        validate_student_id(sid)
    assert exc.value.code == RejectionCode.INVALID_STUDENT_ID


def test_prefer_hyphen_only_for_new_ids():
    assert prefer_hyphen_separator("S1234/0123") == "S1234-0123"
    # existing hyphen id untouched
    assert prefer_hyphen_separator("S1234-0123") == "S1234-0123"


def test_build_natural_key_total():
    nk = build_natural_key("FTNA-2026", "S1234-0123", "011", "THEORY1")
    assert nk == NaturalKey("FTNA-2026", "S1234-0123", "011", PaperType.THEORY1, None)
    assert nk.to_dict() == {
        "exam_code": "FTNA-2026",
        "student_id": "S1234-0123",
        "subject_code": "011",
        "paper_type": "THEORY1",
    }


def test_build_natural_key_item_includes_question():
    nk = build_natural_key("FTNA-2026", "S1234-0123", "011", PaperType.THEORY1, "2a")
    assert nk.question_number == "2a"
    assert nk.to_dict()["question_number"] == "2a"
    assert nk.to_string() == "FTNA-2026|S1234-0123|011|THEORY1|2a"


def test_build_natural_key_unknown_paper():
    with pytest.raises(ValidationError) as exc:
        build_natural_key("FTNA-2026", "S1", "011", "THEORY9")
    assert exc.value.code == RejectionCode.INVALID_NATURAL_KEY


@pytest.mark.parametrize("missing", ["exam_code", "student_id", "subject_code", "paper_type"])
def test_parse_natural_key_missing_field(missing):
    data = {
        "exam_code": "FTNA-2026",
        "student_id": "S1",
        "subject_code": "011",
        "paper_type": "THEORY1",
    }
    del data[missing]
    with pytest.raises(ValidationError) as exc:
        parse_natural_key(data)
    assert exc.value.code == RejectionCode.INVALID_NATURAL_KEY


def test_parse_natural_key_roundtrip():
    data = {
        "exam_code": "FTNA-2026",
        "student_id": "S1234-0123",
        "subject_code": "011",
        "paper_type": "THEORY1",
        "question_number": "1",
    }
    nk = parse_natural_key(data)
    assert nk.to_dict() == data
