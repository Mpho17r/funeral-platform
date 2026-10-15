"""Member archive, personal-data export, anonymising, ID checks and
the audit trail around them."""

import json
import uuid

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.audit_log import AuditLog
from app.models.communication import (
    CommunicationMessage,
    MemberCommunicationPreference,
)
from app.models.covered_dependent import CoveredDependent
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_contribution import MembershipContribution
from app.models.membership_payment import MembershipPayment
from app.models.membership_plan import MembershipPlan
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.services.communications import plan_reminders
from app.services.identity import normalise_identity_number


# Valid South African ID numbers (the last digit is the check digit).
ID_ONE = "9001015009086"
ID_TWO = "9101015009084"


# ============================================================
# HELPERS
# ============================================================

def make_member(db, business, *, id_number=None, number=None, **fields):
    member = Member(
        business_id=business.id,
        member_number=number or f"M-{uuid.uuid4().hex[:8].upper()}",
        first_name=fields.pop("first_name", "Thandi"),
        last_name=fields.pop("last_name", "Nkosi"),
        id_number=id_number,
        phone=fields.pop("phone", "082 123 4567"),
        email=fields.pop("email", "thandi@example.com"),
        address=fields.pop("address", "12 Long Street"),
        date_of_birth=fields.pop("date_of_birth", date(1990, 1, 1)),
        join_date=date(2025, 1, 1),
        status="active",
        **fields,
    )
    db.add(member)
    db.commit()

    return member


def make_plan(db, business):
    plan = MembershipPlan(
        business_id=business.id,
        name=f"Plan {uuid.uuid4().hex[:6]}",
        monthly_contribution=Decimal("250.00"),
        is_active=True,
    )
    db.add(plan)
    db.commit()

    return plan


def make_membership(db, business, member, plan=None, *, status="active"):
    plan = plan or make_plan(db, business)

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MS-{uuid.uuid4().hex[:8].upper()}",
        start_date=date(2025, 1, 1),
        status=status,
    )
    db.add(membership)
    db.commit()

    return membership


def grant(db, role, key):
    permission = db.query(Permission).filter(Permission.key == key).one()

    exists = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if exists is None:
        db.add(RolePermission(role=role, permission_id=permission.id))
        db.commit()


def audit_entries(db, action):
    return (
        db.query(AuditLog)
        .filter(AuditLog.action == action)
        .order_by(AuditLog.created_at)
        .all()
    )


def archive(client, auth_headers, user, member, **params):
    return client.delete(
        f"/members/{member.id}",
        params=params,
        headers=auth_headers(user),
    )


def payload(number="NEW-001", **fields):
    data = {
        "member_number": number,
        "first_name": "Sipho",
        "last_name": "Dlamini",
        "id_number": ID_ONE,
    }
    data.update(fields)

    return data


# ============================================================
# IDENTITY NUMBER RULES
# ============================================================

def test_valid_sa_id_is_kept_and_spaces_are_removed():
    assert normalise_identity_number("900101 5009 086") == ID_ONE


@pytest.mark.parametrize(
    "value",
    [
        "9001015009087",  # wrong check digit
        "900101500908",   # one digit short
        "90010150090866",  # one digit too many
        "9013015009086",  # month 13
        "AB1",            # too short for a passport
        "A1234567890123456789012",  # too long
        "123$456789",     # symbols
    ],
)
def test_bad_identity_numbers_are_rejected(value):
    with pytest.raises(ValueError):
        normalise_identity_number(value)


def test_passport_numbers_are_accepted_and_uppercased():
    assert normalise_identity_number("ab-123456") == "AB123456"


def test_blank_identity_number_becomes_none():
    assert normalise_identity_number("   ") is None
    assert normalise_identity_number(None) is None


def test_create_member_rejects_a_mistyped_id(
    client, test_data, auth_headers
):
    response = client.post(
        "/members",
        json=payload(id_number="9001015009087"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422
    assert "check digit" in response.text


def test_create_member_stores_a_tidied_id(client, test_data, auth_headers):
    response = client.post(
        "/members",
        json=payload(id_number="900101 5009 086"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201
    assert response.json()["id_number"] == ID_ONE


def test_member_without_an_id_is_allowed(client, test_data, auth_headers):
    response = client.post(
        "/members",
        json=payload(id_number=None),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201
    assert response.json()["id_number"] is None


def test_update_member_rejects_a_mistyped_id(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"], id_number=ID_ONE)

    response = client.patch(
        f"/members/{member.id}",
        json={"id_number": "1234567890123"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


def test_the_same_id_cannot_be_on_the_books_twice(
    client, db, test_data, auth_headers
):
    make_member(db, test_data["business_a"], id_number=ID_ONE)

    response = client.post(
        "/members",
        json=payload("DUP-1"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "ID number" in response.json()["detail"]


def test_the_same_id_is_allowed_in_another_business(
    client, db, test_data, auth_headers
):
    make_member(db, test_data["business_b"], id_number=ID_ONE)

    response = client.post(
        "/members",
        json=payload("OK-1"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201


def test_update_cannot_take_another_members_id(
    client, db, test_data, auth_headers
):
    make_member(db, test_data["business_a"], id_number=ID_ONE)
    other = make_member(db, test_data["business_a"], id_number=ID_TWO)

    response = client.patch(
        f"/members/{other.id}",
        json={"id_number": ID_ONE},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409


def test_a_member_can_keep_their_own_id_when_editing(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"], id_number=ID_ONE)

    response = client.patch(
        f"/members/{member.id}",
        json={"id_number": ID_ONE, "first_name": "Thandiwe"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200


def test_the_id_of_an_archived_member_can_be_used_again(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"], id_number=ID_ONE)

    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 204

    response = client.post(
        "/members",
        json=payload("AGAIN-1"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201


def test_dependent_with_a_bad_id_is_rejected(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    membership = make_membership(db, test_data["business_a"], member)

    response = client.post(
        "/covered-dependents",
        json={
            "membership_id": str(membership.id),
            "first_name": "Child",
            "last_name": "Nkosi",
            "relationship": "child",
            "id_number": "9001015009087",
            "cover_start_date": "2025-01-01",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 422


# ============================================================
# ARCHIVE AND RESTORE
# ============================================================

def test_archive_hides_the_member_but_keeps_the_record(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = archive(
        client, auth_headers, test_data["manager"], member,
        reason="Moved away",
    )

    assert response.status_code == 204

    db.expire_all()
    kept = db.get(Member, member.id)

    assert kept is not None
    assert kept.archived_at is not None
    assert kept.archived_by == test_data["manager"].id
    assert kept.archive_reason == "Moved away"


def test_archived_members_are_left_out_of_the_default_list(
    client, db, test_data, auth_headers
):
    keep = make_member(db, test_data["business_a"], number="KEEP")
    gone = make_member(db, test_data["business_a"], number="GONE")
    archive(client, auth_headers, test_data["manager"], gone)

    current = client.get(
        "/members", headers=auth_headers(test_data["manager"])
    ).json()
    archived = client.get(
        "/members?archived=true",
        headers=auth_headers(test_data["manager"]),
    ).json()

    assert [item["id"] for item in current] == [str(keep.id)]
    assert [item["id"] for item in archived] == [str(gone.id)]
    assert archived[0]["archived_at"] is not None


def test_an_archived_member_can_still_be_opened(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member)

    response = client.get(
        f"/members/{member.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["archived_at"] is not None


def test_a_member_with_a_running_membership_cannot_be_archived(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    make_membership(db, test_data["business_a"], member)

    response = archive(client, auth_headers, test_data["manager"], member)

    assert response.status_code == 409
    assert "running membership" in response.json()["detail"]

    db.expire_all()
    assert db.get(Member, member.id).archived_at is None


def test_a_member_in_arrears_cannot_be_archived(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    make_membership(
        db, test_data["business_a"], member, status="arrears"
    )

    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 409


@pytest.mark.parametrize("state", ["cancelled", "lapsed"])
def test_a_member_whose_membership_has_ended_can_be_archived(
    client, db, test_data, auth_headers, state
):
    member = make_member(db, test_data["business_a"])
    make_membership(db, test_data["business_a"], member, status=state)

    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 204


def test_archiving_twice_is_refused(client, db, test_data, auth_headers):
    member = make_member(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member)

    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 409


def test_an_archived_member_cannot_be_edited(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member)

    response = client.patch(
        f"/members/{member.id}",
        json={"first_name": "Changed"},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "Restore" in response.json()["detail"]


def test_an_archived_member_cannot_get_a_new_membership(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    plan = make_plan(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member)

    response = client.post(
        "/memberships",
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": "MS-NEW",
            "start_date": "2026-01-01",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "archived" in response.json()["detail"]


def test_archiving_cancels_messages_still_waiting_to_be_sent(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    member = make_member(db, business)

    waiting = CommunicationMessage(
        business_id=business.id,
        member_id=member.id,
        kind="custom",
        channel="whatsapp",
        recipient="+27821234567",
        body="Hello",
        status="queued",
    )
    sent = CommunicationMessage(
        business_id=business.id,
        member_id=member.id,
        kind="custom",
        channel="whatsapp",
        recipient="+27821234567",
        body="Earlier",
        status="sent",
        sent_at=datetime.now(timezone.utc),
    )
    db.add_all([waiting, sent])
    db.commit()

    archive(client, auth_headers, test_data["manager"], member)

    db.expire_all()

    assert db.get(CommunicationMessage, waiting.id).status == "cancelled"
    assert db.get(CommunicationMessage, sent.id).status == "sent"


def test_other_business_cannot_archive_a_member(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = archive(
        client, auth_headers, test_data["other_business_manager"], member
    )

    assert response.status_code == 404

    db.expire_all()
    assert db.get(Member, member.id).archived_at is None


def test_staff_cannot_archive_without_the_permission(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = archive(client, auth_headers, test_data["staff"], member)

    assert response.status_code == 403


def test_restore_brings_the_member_back(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member, reason="x")

    response = client.post(
        f"/members/{member.id}/restore",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["archived_at"] is None
    assert response.json()["archive_reason"] is None

    current = client.get(
        "/members", headers=auth_headers(test_data["manager"])
    ).json()

    assert [item["id"] for item in current] == [str(member.id)]


def test_restoring_a_member_who_is_not_archived_is_refused(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = client.post(
        f"/members/{member.id}/restore",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409


def test_staff_cannot_restore_without_the_permission(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    archive(client, auth_headers, test_data["manager"], member)

    response = client.post(
        f"/members/{member.id}/restore",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_restore_is_refused_when_the_id_was_taken_meanwhile(
    client, db, test_data, auth_headers
):
    business = test_data["business_a"]
    old = make_member(db, business, id_number=ID_ONE)
    archive(client, auth_headers, test_data["manager"], old)
    make_member(db, business, id_number=ID_ONE)

    response = client.post(
        f"/members/{old.id}/restore",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 409
    assert "ID number" in response.json()["detail"]


def test_archived_members_get_no_reminders(db, test_data):
    business = test_data["business_a"]
    business.lapse_after_days = 30
    member = make_member(db, business)
    membership = make_membership(db, business, member)

    db.add(
        MembershipContribution(
            business_id=business.id,
            membership_id=membership.id,
            contribution_period=date.today().replace(day=1),
            amount_due=Decimal("250.00"),
            amount_paid=Decimal("0.00"),
            due_date=date.today() - timedelta(days=3),
            status="due",
        )
    )
    db.commit()

    assert len(plan_reminders(db, business).candidates) == 1

    # Ended memberships are the only ones that can be archived.
    membership.status = "cancelled"
    member.archived_at = date.today()
    db.commit()

    assert plan_reminders(db, business).candidates == []


# ============================================================
# AUDIT TRAIL
# ============================================================

def test_creating_a_member_is_audited_without_personal_details(
    client, db, test_data, auth_headers
):
    response = client.post(
        "/members",
        json=payload("AUD-1", phone="082 555 0000", address="1 Secret Rd"),
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201

    entry = audit_entries(db, "member.created")[0]
    text = json.dumps(entry.details) + (entry.notes or "")

    assert entry.entity_id == uuid.UUID(response.json()["id"])
    assert entry.user_id == test_data["manager"].id
    assert entry.details["member_number"] == "AUD-1"

    for secret in ("Sipho", "Dlamini", ID_ONE, "082 555 0000", "Secret"):
        assert secret not in text


def test_updating_a_member_is_audited_with_values_redacted(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"], id_number=ID_ONE)

    client.patch(
        f"/members/{member.id}",
        json={
            "first_name": "Zanele",
            "phone": "083 999 8888",
            "status": "arrears",
        },
        headers=auth_headers(test_data["manager"]),
    )

    entry = audit_entries(db, "member.updated")[0]
    changes = entry.details["changes"]
    text = json.dumps(entry.details)

    assert changes["first_name"]["changed"] is True
    assert changes["phone"]["changed"] is True
    assert changes["status"] == {"old": "active", "new": "arrears"}
    assert "Zanele" not in text
    assert "083 999 8888" not in text


def test_an_edit_that_changes_nothing_writes_no_audit_entry(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    client.patch(
        f"/members/{member.id}",
        json={"status": "active"},
        headers=auth_headers(test_data["manager"]),
    )

    assert audit_entries(db, "member.updated") == []


def test_archive_and_restore_are_audited(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    archive(
        client, auth_headers, test_data["manager"], member,
        reason="Private reason text",
    )
    client.post(
        f"/members/{member.id}/restore",
        headers=auth_headers(test_data["manager"]),
    )

    archived = audit_entries(db, "member.archived")[0]
    restored = audit_entries(db, "member.restored")[0]

    assert archived.details["reason_given"] is True
    assert "Private reason text" not in json.dumps(archived.details)
    assert restored.entity_id == member.id


def test_creating_a_membership_is_audited(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    plan = make_plan(db, test_data["business_a"])

    response = client.post(
        "/memberships",
        json={
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "membership_number": "MS-AUD",
            "start_date": "2026-01-01",
        },
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 201

    entry = audit_entries(db, "membership.created")[0]

    assert entry.details["membership_number"] == "MS-AUD"
    assert entry.details["plan_id"] == str(plan.id)


def test_deleting_an_unused_plan_is_audited(
    client, db, test_data, auth_headers
):
    plan = make_plan(db, test_data["business_a"])
    plan_id = plan.id

    response = client.delete(
        f"/membership-plans/{plan_id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 204

    entry = audit_entries(db, "membership_plan.deleted")[0]

    assert entry.entity_id == plan_id
    assert entry.details["name"] == plan.name


def test_a_plan_with_members_cannot_be_deleted(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])
    membership = make_membership(db, test_data["business_a"], member)

    response = client.delete(
        f"/membership-plans/{membership.plan_id}",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 409
    assert "Deactivate" in response.json()["detail"]
    assert audit_entries(db, "membership_plan.deleted") == []


def test_changing_branding_is_audited(client, db, test_data, auth_headers):
    business = test_data["business_a"]

    response = client.patch(
        f"/businesses/{business.id}/branding",
        json={
            "logo_url": None,
            "primary_color": "#112233",
            "secondary_color": "#64748b",
            "watermark_url": None,
            "watermark_opacity": 0.05,
            "theme_preference": "dark",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200

    entry = audit_entries(db, "business.branding_updated")[0]

    assert entry.details["changes"]["primary_color"]["new"] == "#112233"
    assert entry.details["changes"]["theme_preference"]["new"] == "dark"


def test_registering_a_business_is_audited(client, db):
    response = client.post(
        "/auth/register",
        json={
            "business_name": "Fresh Funerals",
            "full_name": "Nomsa Owner",
            "email": f"owner-{uuid.uuid4().hex[:6]}@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201

    entry = audit_entries(db, "business.registered")[0]

    assert entry.user_id is not None
    assert "Nomsa" not in json.dumps(entry.details)


# ============================================================
# PERSONAL DATA EXPORT
# ============================================================

def full_member(db, business):
    member = make_member(db, business, id_number=ID_ONE)
    membership = make_membership(db, business, member)

    db.add_all(
        [
            CoveredDependent(
                business_id=business.id,
                membership_id=membership.id,
                first_name="Little",
                last_name="Nkosi",
                relationship="child",
                id_number=ID_TWO,
                date_of_birth=date(2015, 5, 5),
                phone="084 000 1111",
                status="active",
                cover_start_date=date(2025, 1, 1),
            ),
            MembershipBeneficiary(
                business_id=business.id,
                membership_id=membership.id,
                first_name="Bene",
                last_name="Ficiary",
                relationship="spouse",
                id_number=ID_TWO,
                phone="085 000 2222",
                email="bene@example.com",
                share_percent=Decimal("100.00"),
                notes="Prefers calls",
            ),
            MembershipContribution(
                business_id=business.id,
                membership_id=membership.id,
                contribution_period=date(2025, 2, 1),
                amount_due=Decimal("250.00"),
                amount_paid=Decimal("250.00"),
                due_date=date(2025, 2, 1),
                status="paid",
            ),
            MembershipPayment(
                business_id=business.id,
                membership_id=membership.id,
                amount=Decimal("250.00"),
                payment_method="cash",
                payment_date=date(2025, 2, 1),
            ),
            CommunicationMessage(
                business_id=business.id,
                member_id=member.id,
                membership_id=membership.id,
                kind="payment_overdue",
                channel="whatsapp",
                recipient="+27821234567",
                subject="Overdue",
                body="Hello Thandi, you are late",
                status="sent",
                sent_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            ),
            MemberCommunicationPreference(
                business_id=business.id,
                member_id=member.id,
                preferred_channel="sms",
                opted_out=True,
                opted_out_at=datetime(2025, 3, 2, tzinfo=timezone.utc),
                opt_out_reason="Too many messages",
            ),
        ]
    )
    db.commit()

    return member, membership


def test_manager_can_export_everything_held_about_a_member(
    client, db, test_data, auth_headers
):
    member, _ = full_member(db, test_data["business_a"])

    response = client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["member"]["first_name"] == "Thandi"
    assert data["member"]["id_number"] == ID_ONE
    assert len(data["memberships"]) == 1
    assert data["covered_dependents"][0]["first_name"] == "Little"
    assert data["beneficiaries"][0]["email"] == "bene@example.com"
    assert data["contributions"][0]["status"] == "paid"
    assert data["payments"][0]["amount"] == "250.00"
    assert data["communication_preference"]["opted_out"] is True
    assert data["messages"][0]["body"] == "Hello Thandi, you are late"
    assert "generated_at" in data


def test_every_export_is_audited_without_the_data(
    client, db, test_data, auth_headers
):
    member, _ = full_member(db, test_data["business_a"])

    client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["manager"]),
    )

    entry = audit_entries(db, "member.data_exported")[0]
    text = json.dumps(entry.details)

    assert entry.user_id == test_data["manager"].id
    assert entry.details["dependents"] == 1
    assert entry.details["messages"] == 1
    assert "Thandi" not in text
    assert ID_ONE not in text


def test_staff_cannot_export_member_data(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert audit_entries(db, "member.data_exported") == []


def test_other_business_cannot_export_a_members_data(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["other_business_manager"]),
    )

    assert response.status_code == 404


def test_export_for_a_member_with_no_records_is_empty_not_an_error(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json()["memberships"] == []
    assert response.json()["messages"] == []
    assert response.json()["communication_preference"] is None


# ============================================================
# ANONYMISE
# ============================================================

def anonymise(client, auth_headers, user, member, confirm=None):
    return client.post(
        f"/members/{member.id}/anonymise",
        json={"confirm_member_number": confirm or member.member_number},
        headers=auth_headers(user),
    )


def archived_full_member(client, db, test_data, auth_headers):
    member, membership = full_member(db, test_data["business_a"])
    membership.status = "cancelled"
    db.commit()

    assert archive(
        client, auth_headers, test_data["manager"], member
    ).status_code == 204

    return member, membership


def test_only_an_archived_member_can_be_anonymised(
    client, db, test_data, auth_headers
):
    member = make_member(db, test_data["business_a"])

    response = anonymise(
        client, auth_headers, test_data["main_admin"], member
    )

    assert response.status_code == 409
    assert "Archive" in response.json()["detail"]


def test_anonymising_needs_the_member_number_typed_back(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    response = anonymise(
        client, auth_headers, test_data["main_admin"], member,
        confirm="WRONG",
    )

    assert response.status_code == 422

    db.expire_all()
    assert db.get(Member, member.id).anonymised_at is None


def test_a_manager_cannot_anonymise_by_default(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    response = anonymise(
        client, auth_headers, test_data["manager"], member
    )

    assert response.status_code == 403


def test_other_business_cannot_anonymise(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)
    grant(db, "manager", "members.anonymise")

    response = anonymise(
        client, auth_headers, test_data["other_business_manager"], member
    )

    assert response.status_code == 404


def test_anonymising_removes_every_personal_detail(
    client, db, test_data, auth_headers
):
    member, membership = archived_full_member(
        client, db, test_data, auth_headers
    )

    response = anonymise(
        client, auth_headers, test_data["main_admin"], member
    )

    assert response.status_code == 200

    body = response.json()

    assert body["first_name"] == "Anonymised"
    assert body["last_name"] == "Member"
    assert body["id_number"] is None
    assert body["date_of_birth"] is None
    assert body["phone"] is None
    assert body["email"] is None
    assert body["address"] is None
    assert body["anonymised_at"] is not None

    db.expire_all()

    dependent = db.query(CoveredDependent).one()
    beneficiary = db.query(MembershipBeneficiary).one()
    message = db.query(CommunicationMessage).one()
    preference = db.query(MemberCommunicationPreference).one()

    assert dependent.first_name == "Anonymised"
    assert dependent.id_number is None
    assert dependent.date_of_birth is None
    assert dependent.phone is None
    assert beneficiary.first_name == "Anonymised"
    assert beneficiary.id_number is None
    assert beneficiary.email is None
    assert beneficiary.notes is None
    assert message.recipient == "[removed]"
    assert message.body == "[removed]"
    assert message.subject is None
    assert preference.opt_out_reason is None


def test_anonymising_keeps_the_financial_records(
    client, db, test_data, auth_headers
):
    member, membership = archived_full_member(
        client, db, test_data, auth_headers
    )

    anonymise(client, auth_headers, test_data["main_admin"], member)

    db.expire_all()

    payment = db.query(MembershipPayment).one()
    contribution = db.query(MembershipContribution).one()

    assert payment.amount == Decimal("250.00")
    assert contribution.amount_paid == Decimal("250.00")
    assert db.get(Membership, membership.id) is not None
    assert db.get(Member, member.id).member_number == member.member_number


def test_anonymising_twice_is_refused(client, db, test_data, auth_headers):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    anonymise(client, auth_headers, test_data["main_admin"], member)

    response = anonymise(
        client, auth_headers, test_data["main_admin"], member
    )

    assert response.status_code == 409
    assert "already" in response.json()["detail"]


def test_an_anonymised_member_cannot_be_restored(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    anonymise(client, auth_headers, test_data["main_admin"], member)

    response = client.post(
        f"/members/{member.id}/restore",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 409
    assert "permanently removed" in response.json()["detail"]


def test_an_anonymised_member_exports_nothing_personal(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    anonymise(client, auth_headers, test_data["main_admin"], member)

    response = client.get(
        f"/members/{member.id}/personal-data",
        headers=auth_headers(test_data["main_admin"]),
    )

    text = response.text

    assert response.status_code == 200
    assert "Thandi" not in text
    assert ID_ONE not in text
    assert "bene@example.com" not in text


def test_anonymising_is_audited_without_personal_details(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)

    anonymise(client, auth_headers, test_data["main_admin"], member)

    entry = audit_entries(db, "member.anonymised")[0]
    text = json.dumps(entry.details)

    assert entry.user_id == test_data["main_admin"].id
    assert entry.details["dependents"] == 1
    assert entry.details["beneficiaries"] == 1
    assert entry.details["messages"] == 1
    assert "Thandi" not in text
    assert ID_ONE not in text


def test_a_manager_granted_the_permission_can_anonymise(
    client, db, test_data, auth_headers
):
    member, _ = archived_full_member(client, db, test_data, auth_headers)
    grant(db, "manager", "members.anonymise")

    response = anonymise(
        client, auth_headers, test_data["manager"], member
    )

    assert response.status_code == 200
