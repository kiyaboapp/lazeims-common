"""Pure, database-independent validation rules for LAZEIMS.

Import from here; the submodule layout is an implementation detail.
"""

from __future__ import annotations

from .attendance import (
    AttendanceRow,
    effective_attendance,
    has_specific_transcription,
)
from .config import (
    PaperConfig,
    QuestionConfig,
    QuestionGroupConfig,
    TopicWeight,
    as_decimal,
)
from .marks import (
    validate_item_marks,
    validate_marks_submission,
    validate_total_mark,
)
from .scope import (
    ScopeBlocker,
    ScopeCompletenessResult,
    StudentScopeState,
    evaluate_scope_completeness,
)
from .scoring import (
    compute_paper_total,
    validate_paper_config,
    validate_topic_weights,
)

__all__ = [
    "AttendanceRow",
    "effective_attendance",
    "has_specific_transcription",
    "PaperConfig",
    "QuestionConfig",
    "QuestionGroupConfig",
    "TopicWeight",
    "as_decimal",
    "validate_item_marks",
    "validate_marks_submission",
    "validate_total_mark",
    "ScopeBlocker",
    "ScopeCompletenessResult",
    "StudentScopeState",
    "evaluate_scope_completeness",
    "compute_paper_total",
    "validate_paper_config",
    "validate_topic_weights",
]
