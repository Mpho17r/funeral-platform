from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.case_archival import archive_case, restore_case


def make_case(
    *,
    status: str = "closed",
    is_archived: bool = False,
):
    """
    Lightweight case object for testing the archival service rules.
    """
    case = type("CaseStub", (), {})()
    case.id = uuid4()
    case.business_id = uuid4()
    case.case_number = "LFC-TEST-0001"
    case.status = status
    case.is_archived = is_archived
    case.archived_at = None
    case.archived_by = None
    return case


class AuditRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


@pytest.fixture
def audit_recorder(monkeypatch):
    recorder = AuditRecorder()

    monkeypatch.setattr(
        "app.services.case_archival.create_audit_log",
        recorder,
    )

    return recorder


def test_archive_closed_case(audit_recorder):
    case = make_case(status="closed")
    business_id = uuid4()
    user_id = uuid4()

    result = archive_case(
        None,
        case=case,
        business_id=business_id,
        user_id=user_id,
    )

    assert result is case
    assert case.is_archived is True
    assert case.archived_at is not None
    assert case.archived_at.tzinfo is not None
    assert case.archived_at.tzinfo.utcoffset(case.archived_at) is not None
    assert case.archived_by == user_id

    assert len(audit_recorder.calls) == 1

    _, kwargs = audit_recorder.calls[0]

    assert kwargs["business_id"] == business_id
    assert kwargs["user_id"] == user_id
    assert kwargs["action"] == "case.archived"
    assert kwargs["entity_type"] == "case"
    assert kwargs["entity_id"] == case.id
    assert kwargs["details"] == {
        "status": "closed",
        "archived": True,
    }


def test_archive_cancelled_case(audit_recorder):
    case = make_case(status="cancelled")

    archive_case(
        None,
        case=case,
        business_id=uuid4(),
        user_id=uuid4(),
    )

    assert case.is_archived is True
    assert case.archived_at is not None
    assert case.archived_by is not None
    assert len(audit_recorder.calls) == 1


@pytest.mark.parametrize(
    "case_status",
    [
        "open",
        "confirmed",
        "in_progress",
        "completed",
    ],
)
def test_cannot_archive_non_terminal_case(case_status, audit_recorder):
    case = make_case(status=case_status)

    with pytest.raises(HTTPException) as exc_info:
        archive_case(
            None,
            case=case,
            business_id=uuid4(),
            user_id=uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert "cannot be archived" in exc_info.value.detail

    assert case.is_archived is False
    assert case.archived_at is None
    assert case.archived_by is None
    assert audit_recorder.calls == []


def test_cannot_archive_already_archived_case(audit_recorder):
    case = make_case(
        status="closed",
        is_archived=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        archive_case(
            None,
            case=case,
            business_id=uuid4(),
            user_id=uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Case is already archived"

    assert audit_recorder.calls == []


def test_restore_archived_closed_case(audit_recorder):
    original_archived_at = datetime.now(timezone.utc)
    original_archived_by = uuid4()

    case = make_case(
        status="closed",
        is_archived=True,
    )
    case.archived_at = original_archived_at
    case.archived_by = original_archived_by

    business_id = uuid4()
    user_id = uuid4()

    result = restore_case(
        None,
        case=case,
        business_id=business_id,
        user_id=user_id,
    )

    assert result is case
    assert case.is_archived is False
    assert case.archived_at is None
    assert case.archived_by is None

    # Restore must not alter operational status.
    assert case.status == "closed"

    assert len(audit_recorder.calls) == 1

    _, kwargs = audit_recorder.calls[0]

    assert kwargs["business_id"] == business_id
    assert kwargs["user_id"] == user_id
    assert kwargs["action"] == "case.restored"
    assert kwargs["entity_type"] == "case"
    assert kwargs["entity_id"] == case.id
    assert kwargs["details"] == {
        "status": "closed",
        "archived": False,
    }


def test_restore_archived_cancelled_case(audit_recorder):
    case = make_case(
        status="cancelled",
        is_archived=True,
    )
    case.archived_at = datetime.now(timezone.utc)
    case.archived_by = uuid4()

    restore_case(
        None,
        case=case,
        business_id=uuid4(),
        user_id=uuid4(),
    )

    assert case.is_archived is False
    assert case.archived_at is None
    assert case.archived_by is None

    # Restore must preserve cancelled status.
    assert case.status == "cancelled"

    assert len(audit_recorder.calls) == 1


def test_cannot_restore_active_case(audit_recorder):
    case = make_case(
        status="closed",
        is_archived=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        restore_case(
            None,
            case=case,
            business_id=uuid4(),
            user_id=uuid4(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Case is not archived"

    assert case.is_archived is False
    assert case.archived_at is None
    assert case.archived_by is None
    assert audit_recorder.calls == []


def test_archive_does_not_change_operational_status(audit_recorder):
    case = make_case(status="closed")

    archive_case(
        None,
        case=case,
        business_id=uuid4(),
        user_id=uuid4(),
    )

    assert case.status == "closed"


def test_restore_does_not_change_operational_status(audit_recorder):
    case = make_case(
        status="cancelled",
        is_archived=True,
    )

    restore_case(
        None,
        case=case,
        business_id=uuid4(),
        user_id=uuid4(),
    )

    assert case.status == "cancelled"
