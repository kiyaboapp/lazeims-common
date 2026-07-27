from __future__ import annotations

from lazeims_common.enums import RejectionCode
from lazeims_common.validation.scope import (
    StudentScopeState,
    evaluate_scope_completeness,
)


def test_complete_scope_ok():
    students = [
        StudentScopeState("S1", is_present=True, has_complete_marks=True, has_open_incident=False),
        StudentScopeState("S2", is_present=False, has_complete_marks=False, has_open_incident=False),
    ]
    result = evaluate_scope_completeness(students)
    assert result.complete is True
    assert result.blockers == ()


def test_present_incomplete_no_incident_blocks():
    students = [StudentScopeState("S1", True, False, False)]
    result = evaluate_scope_completeness(students)
    assert result.complete is False
    assert result.blockers[0].code == RejectionCode.BLANK_MARK_NOT_ALLOWED


def test_present_incomplete_with_incident_blocks_on_incident():
    students = [StudentScopeState("S1", True, False, True)]
    result = evaluate_scope_completeness(students)
    assert result.complete is False
    assert result.blockers[0].code == RejectionCode.UNRESOLVED_INCIDENT


def test_complete_but_open_incident_still_blocks():
    students = [StudentScopeState("S1", True, True, True)]
    result = evaluate_scope_completeness(students)
    assert result.complete is False
    assert result.blockers[0].code == RejectionCode.UNRESOLVED_INCIDENT


def test_scope_wide_unresolved_incident_blocks():
    students = [StudentScopeState("S1", True, True, False)]
    result = evaluate_scope_completeness(students, has_unresolved_scope_incident=True)
    assert result.complete is False
    assert any(b.code == RejectionCode.UNRESOLVED_INCIDENT for b in result.blockers)


def test_absent_never_blocks():
    students = [StudentScopeState("S1", False, False, False)]
    assert evaluate_scope_completeness(students).complete is True
