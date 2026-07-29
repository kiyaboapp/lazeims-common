from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from lazeims_common.enums import FillingMode, PaperType, SyncEntityType
from lazeims_common.schemas import (
    AttendanceIn,
    StationPackageManifest,
    StudentPaperMarksIn,
    SyncEvent,
    SyncRequest,
    SyncResponse,
)


def test_attendance_in_valid():
    a = AttendanceIn(
        student_id="S1234-0123",
        subject_code="011",
        paper_type=PaperType.THEORY1,
        is_present=True,
        source="INVIGILATOR_ISAL_TRANSCRIPTION",
    )
    assert a.paper_type == PaperType.THEORY1


def test_attendance_in_forbids_extra():
    with pytest.raises(PydanticValidationError):
        AttendanceIn(
            student_id="S1",
            subject_code="011",
            paper_type=PaperType.THEORY1,
            is_present=True,
            source="INVIGILATOR_ISAL_TRANSCRIPTION",
            junk=1,
        )


def test_item_mark_negative_rejected():
    with pytest.raises(PydanticValidationError):
        StudentPaperMarksIn(
            student_id="S1",
            subject_code="011",
            paper_type=PaperType.THEORY1,
            mode=FillingMode.ITEM_LEVEL,
            items=[{"question_number": "1", "marks": -1}],
        )


def test_student_paper_marks_item_map():
    m = StudentPaperMarksIn(
        student_id="S1",
        subject_code="011",
        paper_type=PaperType.THEORY1,
        mode=FillingMode.ITEM_LEVEL,
        items=[{"question_number": "1", "marks": 8}, {"question_number": "2", "marks": 0}],
    )
    assert m.item_map() == {"1": 8, "2": 0}


def test_sync_request_batch_bounds():
    ev = SyncEvent(
        event_id="evt_1",
        entity_type=SyncEntityType.STUDENT_PAPER_MARKS_REPLACED,
        natural_key={"exam_id": "FTNA-2026", "student_id": "S1", "subject_code": "011", "paper_type": "THEORY1"},
        value={"mode": "TOTAL_MARKS", "total": 67},
        local_version=1,
        actor_assignment_id="assign_1",
        occurred_at=datetime.now(timezone.utc),
    )
    req = SyncRequest(
        station_code="STATION-05",
        exam_id="FTNA-2026",
        package_id="pkg_1",
        package_version=3,
        rules_version="1.0",
        events=[ev],
    )
    assert len(req.events) == 1


def test_sync_request_empty_batch_rejected():
    with pytest.raises(PydanticValidationError):
        SyncRequest(
            station_code="STATION-05",
            exam_id="FTNA-2026",
            package_id="pkg_1",
            package_version=3,
            rules_version="1.0",
            events=[],
        )


def test_sync_response_defaults():
    resp = SyncResponse(server_time=datetime.now(timezone.utc))
    assert resp.accepted == [] and resp.duplicates == [] and resp.rejected == []


def test_station_package_manifest_defaults_contract_version():
    m = StationPackageManifest(
        package_id="pkg_1",
        package_version=3,
        rules_version="1.0",
        software_min_version="1.0.0",
        station_code="STATION-05",
        exam_id="FTNA-2026",
        configuration_hash="sha256:abc",
        issued_at=datetime.now(timezone.utc),
        scope={"schools": ["S1234"], "subjects": ["011"], "papers": ["THEORY1"]},
    )
    assert m.contract_version == "station-package/v1"
    assert m.scope.schools == ["S1234"]
