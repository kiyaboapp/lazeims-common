"""Scope-level completeness for the finalize sweep.

Individual saves validate one student at a time. Finalizing a whole
``(exam, school, subject, paper)`` scope is a separate, stricter check:

  * every registered+present student must have complete marks;
  * no student may be missing a required value without an OPEN/UNDER_REVIEW
    incident explaining it;
  * no unresolved incident may exist for the scope.

This module returns a structured result (it does not raise) so callers can show
every blocking reason at once, then decide whether to write a FinalizedScope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..enums import RejectionCode


@dataclass(frozen=True, slots=True)
class ScopeBlocker:
    code: RejectionCode
    message: str
    student_id: str | None = None


@dataclass(frozen=True, slots=True)
class ScopeCompletenessResult:
    complete: bool
    blockers: tuple[ScopeBlocker, ...] = ()

    def as_dict(self) -> dict:
        return {
            "complete": self.complete,
            "blockers": [
                {"code": b.code.value, "message": b.message, "student_id": b.student_id}
                for b in self.blockers
            ],
        }


@dataclass(frozen=True, slots=True)
class StudentScopeState:
    """Per-student summary the caller assembles from persisted data."""

    student_id: str
    is_present: bool
    has_complete_marks: bool
    has_open_incident: bool


def evaluate_scope_completeness(
    students: list[StudentScopeState],
    *,
    has_unresolved_scope_incident: bool = False,
) -> ScopeCompletenessResult:
    """Evaluate whether a scope may be finalized.

    Rules:
      * A present student without complete marks and without an open incident
        blocks finalize (``BLANK_MARK_NOT_ALLOWED``).
      * A present student who is incomplete but HAS an open incident does not
        block on completeness, but the unresolved incident itself blocks
        (``UNRESOLVED_INCIDENT``) until resolved/escalated.
      * Any unresolved scope-wide incident blocks (``UNRESOLVED_INCIDENT``).
      * Absent students are expected to have no marks; they never block.
    """
    blockers: list[ScopeBlocker] = []

    for s in students:
        if not s.is_present:
            continue
        if not s.has_complete_marks:
            if s.has_open_incident:
                blockers.append(
                    ScopeBlocker(
                        RejectionCode.UNRESOLVED_INCIDENT,
                        f"Student {s.student_id} has an unresolved incident that must be resolved before finalize.",
                        s.student_id,
                    )
                )
            else:
                blockers.append(
                    ScopeBlocker(
                        RejectionCode.BLANK_MARK_NOT_ALLOWED,
                        f"Present student {s.student_id} has incomplete marks and no incident explaining why.",
                        s.student_id,
                    )
                )
        elif s.has_open_incident:
            blockers.append(
                ScopeBlocker(
                    RejectionCode.UNRESOLVED_INCIDENT,
                    f"Student {s.student_id} has an unresolved incident that must be resolved before finalize.",
                    s.student_id,
                )
            )

    if has_unresolved_scope_incident:
        blockers.append(
            ScopeBlocker(
                RejectionCode.UNRESOLVED_INCIDENT,
                "The scope has an unresolved incident and cannot be finalized.",
            )
        )

    return ScopeCompletenessResult(complete=not blockers, blockers=tuple(blockers))
