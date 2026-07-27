"""Shared enumerations for LAZEIMS.

Every enum here is part of the versioned contract between Central and Station.
Adding a member is backward compatible; removing/renaming one is a breaking
change and must go through a contract version bump.
"""

from __future__ import annotations

from enum import Enum


class PaperType(str, Enum):
    """A paper within a subject. ``ALL`` is only valid for an attendance
    baseline row (a subject-wide CAL transcription), never for a mark."""

    THEORY1 = "THEORY1"
    THEORY2 = "THEORY2"
    PRACTICAL = "PRACTICAL"
    ALL = "ALL"

    @classmethod
    def real_papers(cls) -> tuple["PaperType", ...]:
        """Papers that can carry marks (excludes the ``ALL`` baseline)."""
        return (cls.THEORY1, cls.THEORY2, cls.PRACTICAL)


class AttendanceSource(str, Enum):
    """Which paper document an attendance row was transcribed from."""

    INVIGILATOR_ISAL_TRANSCRIPTION = "INVIGILATOR_ISAL_TRANSCRIPTION"
    SUPERVISOR_CAL_TRANSCRIPTION = "SUPERVISOR_CAL_TRANSCRIPTION"


class IncidentType(str, Enum):
    MISSING_SCRIPT = "MISSING_SCRIPT"
    ATTENDANCE_MISMATCH = "ATTENDANCE_MISMATCH"
    ILLNESS_OR_DISTURBANCE = "ILLNESS_OR_DISTURBANCE"
    OTHER = "OTHER"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"

    @classmethod
    def unresolved(cls) -> tuple["IncidentStatus", ...]:
        """Statuses that block finalization/closeout."""
        return (cls.OPEN, cls.UNDER_REVIEW)


class ExamPhase(str, Enum):
    """Authoritative exam lifecycle. This delivery implements transitions
    through ``ENTRY_LOCKED`` only; the remaining values are reserved so the
    data model stays forward-compatible with a future processing release."""

    REGISTRATION = "REGISTRATION"
    ENTRY_OPEN = "ENTRY_OPEN"
    ENTRY_LOCKED = "ENTRY_LOCKED"
    PROCESSING = "PROCESSING"
    RESULTS_PUBLISHED = "RESULTS_PUBLISHED"
    ARCHIVED = "ARCHIVED"


class FillingMode(str, Enum):
    TOTAL_MARKS = "TOTAL_MARKS"
    ITEM_LEVEL = "ITEM_LEVEL"


class DisplayMode(str, Enum):
    NAME = "NAME"
    ID_ONLY = "ID_ONLY"


class WriterMode(str, Enum):
    """The single writer channel that owns a scope at a time."""

    ONLINE = "ONLINE"
    STATION = "STATION"
    EXCEL = "EXCEL"


class SchoolType(str, Enum):
    GOVERNMENT = "GOVERNMENT"
    PRIVATE = "PRIVATE"
    UNKNOWN = "UNKNOWN"


class Sex(str, Enum):
    F = "F"
    M = "M"


class SyncEntityType(str, Enum):
    """Coarse-grained sync events (§11.1 of the delivery plan). These replace
    the guide's illustrative per-row events so a student-paper record can only
    ever be applied completely or not at all."""

    ATTENDANCE_TRANSCRIBED = "ATTENDANCE_TRANSCRIBED"
    INCIDENT_RAISED = "INCIDENT_RAISED"
    STUDENT_PAPER_MARKS_REPLACED = "STUDENT_PAPER_MARKS_REPLACED"
    SCOPE_FINALIZED = "SCOPE_FINALIZED"


class SyncOperation(str, Enum):
    UPSERT = "UPSERT"


class EventStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"


class RejectionCode(str, Enum):
    """Stable, machine-readable rejection codes. The station shows a specific,
    actionable message per code, so these strings must never change meaning."""

    UPGRADE_REQUIRED = "UPGRADE_REQUIRED"
    PACKAGE_REVOKED = "PACKAGE_REVOKED"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    OUTSIDE_STATION_SCOPE = "OUTSIDE_STATION_SCOPE"
    WRITER_MODE_MISMATCH = "WRITER_MODE_MISMATCH"
    ATTENDANCE_REQUIRED_FIRST = "ATTENDANCE_REQUIRED_FIRST"
    BLANK_MARK_NOT_ALLOWED = "BLANK_MARK_NOT_ALLOWED"
    MARK_OUT_OF_RANGE = "MARK_OUT_OF_RANGE"
    ABSENT_STUDENT_HAS_MARKS = "ABSENT_STUDENT_HAS_MARKS"
    SCOPE_ALREADY_FINALIZED = "SCOPE_ALREADY_FINALIZED"
    UNRESOLVED_INCIDENT = "UNRESOLVED_INCIDENT"
    DEPENDENCY_NOT_ACCEPTED = "DEPENDENCY_NOT_ACCEPTED"
    EVENT_ID_PAYLOAD_CONFLICT = "EVENT_ID_PAYLOAD_CONFLICT"
    # Configuration-time validation
    INCOMPLETE_QUESTION_SET = "INCOMPLETE_QUESTION_SET"
    TOPIC_WEIGHT_SUM_INVALID = "TOPIC_WEIGHT_SUM_INVALID"
    NOT_REGISTERED = "NOT_REGISTERED"
    INVALID_STUDENT_ID = "INVALID_STUDENT_ID"
    INVALID_NATURAL_KEY = "INVALID_NATURAL_KEY"
    DUPLICATE_QUESTION = "DUPLICATE_QUESTION"
