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


def test_arrangement_confirmation_updates_case_status_through_api(
    client, db, test_data, auth_headers
):
    from datetime import date
    from uuid import uuid4

    case = FuneralCase(
        business_id=test_data["business_a"].id,
        case_number=f"AUTO-API-{uuid4().hex[:8]}",
        deceased_full_name="API Lifecycle Test",
        date_of_death=date.today() - timedelta(days=3),
        status="open",
    )
    db.add(case)
    db.commit()

    headers = auth_headers(test_data["manager"])
    now = datetime.now(timezone.utc)
    plan = {
        "wake_at": (now - timedelta(days=1)).isoformat(),
        "wake_venue": "Family home",
        "service_at": (now - timedelta(hours=4)).isoformat(),
        "service_venue_type": "church",
        "service_venue": "Test Church",
        "departure_at": (now - timedelta(hours=3)).isoformat(),
        "departure_point": "Test Church",
        "committal_at": (now - timedelta(hours=2)).isoformat(),
        "committal_place": "Test Cemetery",
    }
    created = client.post(
        f"/cases/{case.id}/arrangement", json=plan, headers=headers
    )
    assert created.status_code == 201, created.text

    confirmed = client.post(
        f"/cases/{case.id}/arrangement/transition",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    db.refresh(case)

    assert confirmed.json()["status"] == "confirmed"
    assert case.status == "in_progress"

    completed = client.post(
        f"/cases/{case.id}/arrangement/transition",
        json={"status": "completed"},
        headers=headers,
    )
    assert completed.status_code == 200, completed.text
    db.refresh(case)

    assert completed.json()["status"] == "completed"
    assert case.status == "completed"


def test_scheduled_job_advances_past_confirmed_cases(db, test_data):
    from app.jobs.sync_case_lifecycle import run

    case, arrangement = make_lifecycle_pair(db, test_data["business_a"])
    changed = run(db)
    db.refresh(case)

    assert changed >= 2
    assert case.status == "in_progress"


def test_confirmed_arrangement_without_a_committal_time_still_confirms_case(
    db, test_data
):
    case, arrangement = make_lifecycle_pair(db, test_data["business_a"])
    arrangement.committal_at = None
    db.commit()
    changes = sync_case_status_from_arrangement(
        db, case=case, arrangement=arrangement
    )
    assert changes == [("open", "confirmed")]
    assert case.status == "confirmed"   # but never started on a guess


def test_looking_at_a_case_moves_it_on_without_the_background_job(
    client, auth_headers, db, test_data
):
    case, _ = make_lifecycle_pair(db, test_data["business_a"])  # committal passed
    assert case.status == "open"
    h = auth_headers(test_data["main_admin"])
    got = client.get(f"/cases/{case.id}", headers=h)
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "in_progress"


def test_the_case_list_also_refreshes_stuck_cases(
    client, auth_headers, db, test_data
):
    case, _ = make_lifecycle_pair(db, test_data["business_a"])
    h = auth_headers(test_data["main_admin"])
    rows = client.get("/cases", headers=h).json()
    assert {r["id"]: r["status"] for r in rows}[str(case.id)] == "in_progress"
