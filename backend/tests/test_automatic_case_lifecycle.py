from datetime import datetime, timedelta, timezone

from app.models.arrangement import FuneralArrangement
from app.models.funeral_case import FuneralCase
from app.services.automatic_case_lifecycle import (
    sync_case_status_from_arrangement,
)


def make_lifecycle_pair(db, business, *, case_status="open",
                        arrangement_status="confirmed",
                        committal_at=None, archived=False):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"AUTO-{datetime.now(timezone.utc).timestamp()}",
        deceased_full_name="Automatic Lifecycle Test",
        status=case_status,
        is_archived=archived,
    )
    db.add(case)
    db.flush()

    arrangement = FuneralArrangement(
        business_id=business.id,
        case_id=case.id,
        status=arrangement_status,
        committal_at=committal_at or datetime.now(timezone.utc) - timedelta(hours=2),
        committal_place="Test Cemetery",
        created_by=None,
    )
    db.add(arrangement)
    db.commit()
    return case, arrangement


def test_confirmed_future_arrangement_confirms_case_without_starting_it(db, test_data):
    future = datetime.now(timezone.utc) + timedelta(days=2)
    case, arrangement = make_lifecycle_pair(
        db, test_data["business_a"], committal_at=future
    )

    changed = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    db.commit()

    assert changed == [("open", "confirmed")]
    assert case.status == "confirmed"


def test_passed_confirmed_arrangement_moves_case_to_in_progress(db, test_data):
    case, arrangement = make_lifecycle_pair(db, test_data["business_a"])

    changed = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    db.commit()

    assert changed == [("open", "confirmed"), ("confirmed", "in_progress")]
    assert case.status == "in_progress"


def test_completed_arrangement_advances_case_through_each_status(db, test_data):
    case, arrangement = make_lifecycle_pair(
        db, test_data["business_a"], arrangement_status="completed"
    )

    changed = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    db.commit()

    assert changed == [
        ("open", "confirmed"),
        ("confirmed", "in_progress"),
        ("in_progress", "completed"),
    ]
    assert case.status == "completed"


def test_draft_arrangement_does_not_advance_case(db, test_data):
    case, arrangement = make_lifecycle_pair(
        db, test_data["business_a"], arrangement_status="draft"
    )

    changed = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    db.commit()

    assert changed == []
    assert case.status == "open"


def test_cancelled_or_archived_case_is_never_auto_advanced(db, test_data):
    case, arrangement = make_lifecycle_pair(
        db, test_data["business_a"], case_status="cancelled"
    )
    changed = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    assert changed == []
    assert case.status == "cancelled"

    archived_case, archived_arrangement = make_lifecycle_pair(
        db, test_data["business_a"], archived=True
    )
    changed = sync_case_status_from_arrangement(
        db, case=archived_case, arrangement=archived_arrangement
    )
    assert changed == []
    assert archived_case.status == "open"
