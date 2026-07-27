"""Plain, database-independent value objects describing exam configuration.

Central builds these from its ORM rows; Station builds them from the package
seed. The validation functions in this subpackage operate ONLY on these value
objects and plain input, so a rule is identical on both sides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..enums import PaperType


def as_decimal(value) -> Decimal:
    """Coerce a numeric value to Decimal without float artefacts."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # guard: bool is an int subclass
        raise TypeError("boolean is not a valid mark value")
    if isinstance(value, int):
        return Decimal(value)
    # Route floats/strings through str() to avoid binary float noise.
    return Decimal(str(value))


@dataclass(frozen=True, slots=True)
class TopicWeight:
    topic_code: str
    weight: Decimal


@dataclass(frozen=True, slots=True)
class QuestionConfig:
    """One configured question within a paper."""

    question_number: str
    max_marks: Decimal
    group_code: str | None = None  # None => compulsory
    topics: tuple[TopicWeight, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestionGroupConfig:
    """A 'answer any N of M' group."""

    code: str
    pick_count: int


@dataclass(frozen=True, slots=True)
class PaperConfig:
    """Full scoring configuration for one paper of one subject."""

    paper_type: PaperType
    paper_max: Decimal
    questions: tuple[QuestionConfig, ...] = ()
    groups: tuple[QuestionGroupConfig, ...] = ()

    def question_map(self) -> dict[str, QuestionConfig]:
        return {q.question_number: q for q in self.questions}

    def group_map(self) -> dict[str, QuestionGroupConfig]:
        return {g.code: g for g in self.groups}

    def required_question_numbers(self) -> list[str]:
        """All configured question numbers (compulsory + grouped).

        In item mode every configured question must have an explicit value.
        """
        return [q.question_number for q in self.questions]
