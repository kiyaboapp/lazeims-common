from __future__ import annotations

from decimal import Decimal

import pytest

from lazeims_common.enums import PaperType, RejectionCode
from lazeims_common.errors import ValidationError
from lazeims_common.validation.config import (
    PaperConfig,
    QuestionConfig,
    QuestionGroupConfig,
    TopicWeight,
)
from lazeims_common.validation.scoring import (
    compute_paper_total,
    validate_paper_config,
    validate_topic_weights,
)


# ---- topic weights ----

def test_topic_weights_sum_to_one_ok():
    q = QuestionConfig("1", Decimal("10"), None,
                       (TopicWeight("A", Decimal("0.5")), TopicWeight("B", Decimal("0.5"))))
    validate_topic_weights(q)  # no raise


def test_topic_weights_no_topics_ok():
    validate_topic_weights(QuestionConfig("1", Decimal("10")))


def test_topic_weights_bad_sum_rejected():
    q = QuestionConfig("1", Decimal("10"), None,
                       (TopicWeight("A", Decimal("0.5")), TopicWeight("B", Decimal("0.4"))))
    with pytest.raises(ValidationError) as exc:
        validate_topic_weights(q)
    assert exc.value.code == RejectionCode.TOPIC_WEIGHT_SUM_INVALID


# ---- paper config integrity ----

def test_valid_config_passes(item_paper):
    validate_paper_config(item_paper)


def test_duplicate_question_rejected():
    paper = PaperConfig(
        PaperType.THEORY1, Decimal("20"),
        questions=(QuestionConfig("1", Decimal("10")), QuestionConfig("1", Decimal("10"))),
    )
    with pytest.raises(ValidationError) as exc:
        validate_paper_config(paper)
    assert exc.value.code == RejectionCode.DUPLICATE_QUESTION


def test_question_references_unknown_group():
    paper = PaperConfig(
        PaperType.THEORY1, Decimal("20"),
        questions=(QuestionConfig("1", Decimal("10"), "NOPE"),),
    )
    with pytest.raises(ValidationError) as exc:
        validate_paper_config(paper)
    assert exc.value.code == RejectionCode.INCOMPLETE_QUESTION_SET


def test_group_pick_count_exceeds_members():
    paper = PaperConfig(
        PaperType.THEORY1, Decimal("20"),
        questions=(QuestionConfig("1", Decimal("10"), "B"),),
        groups=(QuestionGroupConfig("B", pick_count=3),),
    )
    with pytest.raises(ValidationError) as exc:
        validate_paper_config(paper)
    assert exc.value.code == RejectionCode.INCOMPLETE_QUESTION_SET


def test_group_pick_count_zero_rejected():
    paper = PaperConfig(
        PaperType.THEORY1, Decimal("40"),
        questions=(QuestionConfig("1", Decimal("20"), "B"), QuestionConfig("2", Decimal("20"), "B")),
        groups=(QuestionGroupConfig("B", pick_count=0),),
    )
    with pytest.raises(ValidationError) as exc:
        validate_paper_config(paper)
    assert exc.value.code == RejectionCode.INCOMPLETE_QUESTION_SET


# ---- best-N-of-M total ----

def test_compute_total_best_n_of_m(item_paper):
    # compulsory 1,2,3 = 10+8+6 = 24
    # group B: scores 20,15,12,0,0 -> best 3 = 20+15+12 = 47
    # total = 71
    marks = {
        "1": Decimal("10"), "2": Decimal("8"), "3": Decimal("6"),
        "4": Decimal("20"), "5": Decimal("15"), "6": Decimal("12"),
        "7": Decimal("0"), "8": Decimal("0"),
    }
    assert compute_paper_total(item_paper, marks) == Decimal("71")


def test_compute_total_picks_highest(item_paper):
    # group all equal-ish; ensure lowest two dropped
    marks = {
        "1": Decimal("0"), "2": Decimal("0"), "3": Decimal("0"),
        "4": Decimal("1"), "5": Decimal("2"), "6": Decimal("3"),
        "7": Decimal("4"), "8": Decimal("5"),
    }
    # best 3 of {1,2,3,4,5} = 5+4+3 = 12
    assert compute_paper_total(item_paper, marks) == Decimal("12")


def test_compute_total_missing_treated_as_zero(item_paper):
    # only compulsory provided; group missing -> 0
    marks = {"1": Decimal("10"), "2": Decimal("10"), "3": Decimal("10")}
    assert compute_paper_total(item_paper, marks) == Decimal("30")
