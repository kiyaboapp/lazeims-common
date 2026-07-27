"""Shared fixtures: representative valid paper configurations."""

from __future__ import annotations

from decimal import Decimal

import pytest

from lazeims_common.enums import PaperType
from lazeims_common.validation.config import (
    PaperConfig,
    QuestionConfig,
    QuestionGroupConfig,
    TopicWeight,
)


@pytest.fixture
def total_paper() -> PaperConfig:
    """A Mode A (total-marks) paper with a max of 100."""
    return PaperConfig(paper_type=PaperType.THEORY1, paper_max=Decimal("100"))


@pytest.fixture
def item_paper() -> PaperConfig:
    """A Mode B paper: 3 compulsory (10 each) + a group 'B' of 5 questions
    (20 each) where the best 3 count. Max plausible total = 30 + 60 = 90,
    paper_max set to 90.
    """
    questions = (
        QuestionConfig("1", Decimal("10"), None, (TopicWeight("COLONIAL", Decimal("1.0")),)),
        QuestionConfig("2", Decimal("10"), None),
        QuestionConfig("3", Decimal("10"), None),
        QuestionConfig("4", Decimal("20"), "B",
                       (TopicWeight("COLONIAL", Decimal("0.5")), TopicWeight("INDEPENDENCE", Decimal("0.5")))),
        QuestionConfig("5", Decimal("20"), "B"),
        QuestionConfig("6", Decimal("20"), "B"),
        QuestionConfig("7", Decimal("20"), "B"),
        QuestionConfig("8", Decimal("20"), "B"),
    )
    groups = (QuestionGroupConfig("B", pick_count=3),)
    return PaperConfig(
        paper_type=PaperType.THEORY1,
        paper_max=Decimal("90"),
        questions=questions,
        groups=groups,
    )
