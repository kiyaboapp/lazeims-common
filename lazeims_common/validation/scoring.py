"""Scoring rules: config-time integrity and paper-total computation.

* Topic weights per question must sum to exactly 1.0 (config time).
* Item mode requires the complete configured question set (entry time).
* Paper total = sum(compulsory) + sum(best ``pick_count`` per group), and must
  not exceed the paper maximum.
"""

from __future__ import annotations

from decimal import Decimal

from ..enums import RejectionCode
from ..errors import ValidationError
from .config import PaperConfig, QuestionConfig, as_decimal

# Weights are fractions; allow a tiny tolerance for representation only.
_WEIGHT_TOLERANCE = Decimal("0.0001")
_ONE = Decimal("1.0")


def validate_topic_weights(question: QuestionConfig) -> None:
    """Per-question topic weights must sum to exactly 1.0.

    A question with no topics is allowed (topics are an analytics-only axis and
    optional per question). If any topic is present, the full set must sum to 1.
    """
    if not question.topics:
        return
    total = sum((as_decimal(t.weight) for t in question.topics), Decimal(0))
    if abs(total - _ONE) > _WEIGHT_TOLERANCE:
        raise ValidationError(
            RejectionCode.TOPIC_WEIGHT_SUM_INVALID,
            f"Topic weights for question {question.question_number} sum to {total}, expected 1.0.",
            {
                "question_number": question.question_number,
                "weight_sum": str(total),
            },
        )


def validate_paper_config(paper: PaperConfig) -> None:
    """Validate a paper's scoring configuration at config-save time.

    * No duplicate question numbers.
    * Every grouped question references an existing group.
    * Each group's ``pick_count`` is >= 1 and does not exceed its member count.
    * Topic weights sum to 1.0 per question.
    """
    seen: set[str] = set()
    group_members: dict[str, int] = {g.code: 0 for g in paper.groups}
    group_codes = set(group_members)

    for q in paper.questions:
        if q.question_number in seen:
            raise ValidationError(
                RejectionCode.DUPLICATE_QUESTION,
                f"Duplicate question number {q.question_number} in paper {paper.paper_type.value}.",
                {"question_number": q.question_number},
            )
        seen.add(q.question_number)

        if q.group_code is not None:
            if q.group_code not in group_codes:
                raise ValidationError(
                    RejectionCode.INCOMPLETE_QUESTION_SET,
                    f"Question {q.question_number} references unknown group '{q.group_code}'.",
                    {"question_number": q.question_number, "group_code": q.group_code},
                )
            group_members[q.group_code] += 1

        validate_topic_weights(q)

    for g in paper.groups:
        members = group_members[g.code]
        if g.pick_count < 1:
            raise ValidationError(
                RejectionCode.INCOMPLETE_QUESTION_SET,
                f"Group '{g.code}' pick_count must be >= 1.",
                {"group_code": g.code, "pick_count": g.pick_count},
            )
        if g.pick_count > members:
            raise ValidationError(
                RejectionCode.INCOMPLETE_QUESTION_SET,
                f"Group '{g.code}' pick_count {g.pick_count} exceeds its {members} member question(s).",
                {"group_code": g.code, "pick_count": g.pick_count, "members": members},
            )


def compute_paper_total(
    paper: PaperConfig, item_marks: dict[str, Decimal | int | float | str]
) -> Decimal:
    """Compute the paper total from item marks using best-N-of-M rules.

    Order (Guide §2.4):
      1. Sum every compulsory question (``group_code is None``).
      2. For each group, sum only the student's ``pick_count`` highest scores.
      3. Add both sums.

    ``item_marks`` maps question_number -> value. All configured questions are
    expected to be present (see :func:`validate_item_marks_complete`); missing
    entries are treated as 0 here so this function is safe to call after
    validation.
    """
    qmap = paper.question_map()
    gmap = paper.group_map()

    compulsory_total = Decimal(0)
    grouped_scores: dict[str, list[Decimal]] = {g.code: [] for g in paper.groups}

    for qnum, q in qmap.items():
        raw = item_marks.get(qnum, 0)
        value = as_decimal(raw)
        if q.group_code is None:
            compulsory_total += value
        else:
            grouped_scores[q.group_code].append(value)

    grouped_total = Decimal(0)
    for code, scores in grouped_scores.items():
        pick = gmap[code].pick_count
        best = sorted(scores, reverse=True)[:pick]
        grouped_total += sum(best, Decimal(0))

    return compulsory_total + grouped_total
