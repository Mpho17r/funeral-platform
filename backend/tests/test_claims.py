import uuid

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_claim import MembershipClaim
from app.models.membership_plan import MembershipPlan
from app.models.membership_plan_benefit import MembershipPlanBenefit
from app.models.permission import Permission
from app.models.user_permission import UserPermission


# ============================================================
# HELPERS
# ============================================================

def set_permission(db, user_id, permission_key, effect):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    db.add(
        UserPermission(
            user_id=user_id,
            permission_id=permission.id,
            effect=effect,
        )
    )
    db.commit()


def make_membership(
    db,
    business,
    *,
    monetary_limit=Decimal("15000.00"),
    status="active",
):
    suffix = uuid.uuid4().hex[:8].upper()

    member = Member(
        business_id=business.id,
        member_number=f"M-{suffix}",
        first_name="Claim",
        last_name="Member",
        join_date=date(2026, 1, 1),
        status="active",
    )
    db.add(member)
    db.flush()

    plan = MembershipPlan(
        business_id=business.id,
        name=f"Plan {suffix}",
        monthly_contribution=Decimal("200.00"),
        is_active=True,
    )
    db.add(plan)
    db.flush()

    if monetary_limit is not None:
        db.add(
            MembershipPlanBenefit(
                business_id=business.id,
                plan_id=plan.id,
                name="Funeral Cover",
                benefit_type="monetary",
                monetary_limit=monetary_limit,
                is_included=True,
                is_active=True,
            )
        )

    membership = Membership(
        business_id=business.id,
        member_id=member.id,
        plan_id=plan.id,
        membership_number=f"MS-{suffix}",
        start_date=date(2026, 1, 1),
        status=status,
    )
    db.add(membership)
    db.commit()

    return membership


def make_case(
    db,
    business,
    membership=None,
    *,
    archived=False,
):
    case = FuneralCase(
        business_id=business.id,
        case_number=f"CLM-CASE-{uuid.uuid4().hex[:8].upper()}",
        membership_id=membership.id if membership else None,
        deceased_full_name="Claim Test",
        date_of_death=date(2026, 10, 1),
        status="open",
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def add_beneficiary(
    db,
    business,
    membership,
    share,
    *,
    first_name="Ben",
    active=True,
):
    beneficiary = MembershipBeneficiary(
        business_id=business.id,
        membership_id=membership.id,
        first_name=first_name,
        last_name="Eficiary",
        relationship="spouse",
        share_percent=Decimal(str(share)),
        is_active=active,
    )
    db.add(beneficiary)
    db.commit()

    return beneficiary


def submit(client, headers, case, amount="10000.00", **extra):
    return client.post(
        "/claims",
        json={
            "case_id": str(case.id),
            "claimed_amount": amount,
            **extra,
        },
        headers=headers,
    )


def approved_claim(
    client,
    headers,
    case,
    amount="10000.00",
):
    claim = submit(client, headers, case, amount).json()

    assert (
        client.post(
            f"/claims/{claim['id']}/review", headers=headers
        ).status_code
        == 200
    )

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": amount},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    return response.json()


def actions(db, business):
    return {
        row.action
        for row in db.query(AuditLog)
        .filter(AuditLog.business_id == business.id)
        .all()
    }


# ============================================================
# BENEFICIARIES
# ============================================================

def test_manager_can_add_beneficiary_and_see_summary(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/memberships/{membership.id}/beneficiaries",
        json={
            "first_name": "Thandi",
            "last_name": "Nkosi",
            "relationship": "spouse",
            "share_percent": "60.00",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["share_percent"] == "60.00"

    summary = client.get(
        f"/memberships/{membership.id}/beneficiaries/summary",
        headers=headers,
    ).json()

    assert summary["active_beneficiaries"] == 1
    assert Decimal(summary["allocated_percent"]) == Decimal("60")
    assert Decimal(summary["remaining_percent"]) == Decimal("40")
    assert summary["is_fully_allocated"] is False

    assert "beneficiary.created" in actions(db, business)


def test_beneficiary_shares_cannot_exceed_100(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    add_beneficiary(db, business, membership, 70)
    headers = auth_headers(test_data["manager"])

    over = client.post(
        f"/memberships/{membership.id}/beneficiaries",
        json={
            "first_name": "A",
            "last_name": "B",
            "relationship": "child",
            "share_percent": "30.01",
        },
        headers=headers,
    )
    assert over.status_code == 409

    exact = client.post(
        f"/memberships/{membership.id}/beneficiaries",
        json={
            "first_name": "A",
            "last_name": "B",
            "relationship": "child",
            "share_percent": "30.00",
        },
        headers=headers,
    )
    assert exact.status_code == 201

    summary = client.get(
        f"/memberships/{membership.id}/beneficiaries/summary",
        headers=headers,
    ).json()
    assert summary["is_fully_allocated"] is True


def test_share_percent_bounds_validated(
    client, test_data, auth_headers, db
):
    membership = make_membership(db, test_data["business_a"])
    headers = auth_headers(test_data["manager"])

    for bad in ("0", "-5", "100.01"):
        response = client.post(
            f"/memberships/{membership.id}/beneficiaries",
            json={
                "first_name": "A",
                "last_name": "B",
                "relationship": "child",
                "share_percent": bad,
            },
            headers=headers,
        )
        assert response.status_code == 422, bad


def test_updating_share_excludes_self_from_total(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    first = add_beneficiary(db, business, membership, 60)
    add_beneficiary(db, business, membership, 40)
    headers = auth_headers(test_data["manager"])

    lower = client.patch(
        f"/beneficiaries/{first.id}",
        json={"share_percent": "50.00"},
        headers=headers,
    )
    assert lower.status_code == 200, lower.text

    higher = client.patch(
        f"/beneficiaries/{first.id}",
        json={"share_percent": "60.01"},
        headers=headers,
    )
    assert higher.status_code == 409


def test_update_audit_redacts_personal_fields(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    beneficiary = add_beneficiary(db, business, membership, 50)

    response = client.patch(
        f"/beneficiaries/{beneficiary.id}",
        json={"first_name": "Renamed", "share_percent": "40.00"},
        headers=auth_headers(test_data["manager"]),
    )
    assert response.status_code == 200

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "beneficiary.updated")
        .one()
    )
    changes = log.details["changes"]

    assert changes["first_name"]["new"] == "[redacted]"
    assert changes["share_percent"]["new"] == "40.00"


def test_deactivating_beneficiary_frees_share_and_is_final(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    beneficiary = add_beneficiary(db, business, membership, 100)
    headers = auth_headers(test_data["manager"])

    response = client.post(
        f"/beneficiaries/{beneficiary.id}/deactivate", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    again = client.post(
        f"/beneficiaries/{beneficiary.id}/deactivate", headers=headers
    )
    assert again.status_code == 409

    edit = client.patch(
        f"/beneficiaries/{beneficiary.id}",
        json={"relationship": "child"},
        headers=headers,
    )
    assert edit.status_code == 409

    replacement = client.post(
        f"/memberships/{membership.id}/beneficiaries",
        json={
            "first_name": "New",
            "last_name": "Person",
            "relationship": "child",
            "share_percent": "100.00",
        },
        headers=headers,
    )
    assert replacement.status_code == 201

    # The deactivated record is retained for history.
    everyone = client.get(
        f"/memberships/{membership.id}/beneficiaries"
        "?include_inactive=true",
        headers=headers,
    ).json()
    assert len(everyone) == 2

    active_only = client.get(
        f"/memberships/{membership.id}/beneficiaries", headers=headers
    ).json()
    assert len(active_only) == 1

    assert "beneficiary.deactivated" in actions(db, business)


def test_staff_can_view_but_not_manage_beneficiaries(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    beneficiary = add_beneficiary(db, business, membership, 50)
    headers = auth_headers(test_data["staff"])

    assert (
        client.get(
            f"/memberships/{membership.id}/beneficiaries",
            headers=headers,
        ).status_code
        == 200
    )

    assert (
        client.post(
            f"/memberships/{membership.id}/beneficiaries",
            json={
                "first_name": "A",
                "last_name": "B",
                "relationship": "child",
                "share_percent": "10",
            },
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/beneficiaries/{beneficiary.id}",
            json={"relationship": "child"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/beneficiaries/{beneficiary.id}/deactivate",
            headers=headers,
        ).status_code
        == 403
    )


def test_beneficiary_tenant_isolation(
    client, test_data, auth_headers, db
):
    other_membership = make_membership(db, test_data["business_b"])
    other_beneficiary = add_beneficiary(
        db, test_data["business_b"], other_membership, 50
    )
    headers = auth_headers(test_data["manager"])

    assert (
        client.get(
            f"/memberships/{other_membership.id}/beneficiaries",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/memberships/{other_membership.id}/beneficiaries",
            json={
                "first_name": "A",
                "last_name": "B",
                "relationship": "child",
                "share_percent": "10",
            },
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/beneficiaries/{other_beneficiary.id}",
            json={"relationship": "x"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/beneficiaries/{other_beneficiary.id}/deactivate",
            headers=headers,
        ).status_code
        == 404
    )


# ============================================================
# CLAIMS: SUBMISSION
# ============================================================

def test_staff_can_submit_claim_with_coverage_snapshot(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    case = make_case(db, business, membership)

    response = submit(
        client,
        auth_headers(test_data["staff"]),
        case,
        notes="Family requested payout",
    )

    assert response.status_code == 201, response.text
    body = response.json()

    year = datetime.now(timezone.utc).year
    assert body["claim_number"] == f"CLM-{year}-00001"
    assert body["status"] == "submitted"
    assert body["membership_id"] == str(membership.id)
    assert body["submitted_by"] == str(test_data["staff"].id)
    assert body["submission_coverage"]["covered"] is True
    assert body["submission_coverage"]["benefits"][0]["name"] == (
        "Funeral Cover"
    )

    assert "claim.submitted" in actions(db, business)


def test_claim_numbers_increase_per_business(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])

    first = submit(
        client, headers, make_case(
            db, business, make_membership(db, business)
        )
    ).json()
    second = submit(
        client, headers, make_case(
            db, business, make_membership(db, business)
        )
    ).json()

    assert first["claim_number"].endswith("00001")
    assert second["claim_number"].endswith("00002")

    # The other business starts its own sequence.
    other_business = test_data["business_b"]
    other = make_case(
        db, other_business, make_membership(db, other_business)
    )
    other_headers = auth_headers(test_data["other_business_manager"])
    other_claim = submit(client, other_headers, other).json()

    assert other_claim["claim_number"].endswith("00001")


def test_claim_requires_membership_linked_case(
    client, test_data, auth_headers, db
):
    case = make_case(db, test_data["business_a"])

    response = submit(
        client, auth_headers(test_data["manager"]), case
    )

    assert response.status_code == 409


def test_claim_rejected_on_archived_case(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    case = make_case(db, business, membership, archived=True)

    response = submit(
        client, auth_headers(test_data["manager"]), case
    )

    assert response.status_code == 409


def test_claim_amount_must_be_positive(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    for bad in ("0", "-1"):
        assert (
            submit(client, headers, case, bad).status_code == 422
        )


def test_only_one_live_claim_per_case(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    first = submit(client, headers, case).json()

    duplicate = submit(client, headers, case)
    assert duplicate.status_code == 409
    assert "live claim" in duplicate.json()["detail"]

    # Cancelling frees the case for a fresh claim.
    cancel = client.post(
        f"/claims/{first['id']}/cancel", json={}, headers=headers
    )
    assert cancel.status_code == 200

    retry = submit(client, headers, case)
    assert retry.status_code == 201, retry.text
    assert retry.json()["claim_number"].endswith("00002")


def test_cannot_claim_against_other_business_case(
    client, test_data, auth_headers, db
):
    other_business = test_data["business_b"]
    other_case = make_case(
        db, other_business, make_membership(db, other_business)
    )

    response = submit(
        client, auth_headers(test_data["manager"]), other_case
    )

    assert response.status_code == 404


def test_claim_permissions_view_and_create(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    staff = test_data["staff"]

    set_permission(db, staff.id, "claims.create", "deny")
    assert (
        submit(client, auth_headers(staff), case).status_code == 403
    )

    set_permission(db, staff.id, "claims.view", "deny")
    assert (
        client.get("/claims", headers=auth_headers(staff)).status_code
        == 403
    )


# ============================================================
# CLAIMS: WORKFLOW
# ============================================================

def test_claim_must_be_reviewed_before_decision(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = submit(client, headers, case).json()

    skip = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "5000"},
        headers=headers,
    )
    assert skip.status_code == 409

    skip_reject = client.post(
        f"/claims/{claim['id']}/reject",
        json={"reason": "No"},
        headers=headers,
    )
    assert skip_reject.status_code == 409

    skip_pay = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "REF"},
        headers=headers,
    )
    assert skip_pay.status_code == 409


def test_staff_cannot_review_approve_or_pay(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    staff_headers = auth_headers(test_data["staff"])

    claim = submit(client, staff_headers, case).json()

    for path, body in (
        ("review", None),
        ("approve", {"approved_amount": "1"}),
        ("reject", {"reason": "x"}),
        ("pay", {"payment_reference": "R"}),
    ):
        response = client.post(
            f"/claims/{claim['id']}/{path}",
            json=body,
            headers=staff_headers,
        )
        assert response.status_code == 403, path


def test_approve_within_limit_records_decision(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case, "12000.00")

    assert claim["status"] == "approved"
    assert claim["approved_amount"] == "12000.00"
    assert claim["override_used"] is False
    assert claim["decided_by"] == str(test_data["manager"].id)
    assert claim["decision_coverage"]["covered"] is True

    assert {"claim.review_started", "claim.approved"} <= actions(
        db, business
    )


def test_approval_above_plan_limit_needs_override(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(
        db, business, monetary_limit=Decimal("10000.00")
    )
    case = make_case(db, business, membership)
    manager_headers = auth_headers(test_data["manager"])

    claim = submit(client, manager_headers, case, "20000.00").json()
    client.post(
        f"/claims/{claim['id']}/review", headers=manager_headers
    )

    blocked = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "20000.00"},
        headers=manager_headers,
    )
    assert blocked.status_code == 409
    assert "monetary limit" in blocked.json()["detail"]

    # A manager without claims.override cannot bypass the limit,
    # even with a reason.
    still_blocked = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "20000.00",
            "override_reason": "Family hardship",
        },
        headers=manager_headers,
    )
    assert still_blocked.status_code == 403

    db.expire_all()
    assert (
        db.query(MembershipClaim).one().status == "under_review"
    )


def test_main_admin_override_is_recorded_and_audited(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(
        db, business, monetary_limit=Decimal("10000.00")
    )
    case = make_case(db, business, membership)
    admin_headers = auth_headers(test_data["main_admin"])

    claim = submit(client, admin_headers, case, "20000.00").json()
    client.post(f"/claims/{claim['id']}/review", headers=admin_headers)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "20000.00",
            "override_reason": "Board approved exception",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["override_used"] is True
    assert body["decision_reason"] == "Board approved exception"

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "claim.approved")
        .one()
    )
    assert log.details["override_used"] is True
    assert log.details["override_reason"] == "Board approved exception"
    assert log.details["override_problems"]


def test_explicit_override_permission_lets_manager_override(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(
        db, business, monetary_limit=Decimal("10000.00")
    )
    case = make_case(db, business, membership)
    manager = test_data["manager"]
    headers = auth_headers(manager)
    set_permission(db, manager.id, "claims.override", "allow")

    claim = submit(client, headers, case, "20000.00").json()
    client.post(f"/claims/{claim['id']}/review", headers=headers)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "20000.00",
            "override_reason": "Exception",
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["override_used"] is True


def test_override_reason_is_ignored_when_nothing_to_override(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = submit(client, headers, case).json()
    client.post(f"/claims/{claim['id']}/review", headers=headers)

    response = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "5000.00",
            "override_reason": "Not needed",
            "note": "Straightforward",
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["override_used"] is False
    assert response.json()["decision_reason"] == "Straightforward"


def test_plan_without_monetary_limit_has_no_cap(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business, monetary_limit=None)
    case = make_case(db, business, membership)
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case, "999999.00")

    assert claim["status"] == "approved"
    assert claim["override_used"] is False


def test_coverage_is_rechecked_at_approval(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    case = make_case(db, business, membership)
    manager_headers = auth_headers(test_data["manager"])

    claim = submit(client, manager_headers, case).json()
    assert claim["submission_coverage"]["covered"] is True

    client.post(
        f"/claims/{claim['id']}/review", headers=manager_headers
    )

    # The membership is cancelled after submission.
    membership.status = "cancelled"
    db.commit()

    blocked = client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "5000.00"},
        headers=manager_headers,
    )
    assert blocked.status_code == 409
    assert "coverage check failed" in blocked.json()["detail"]

    forced = client.post(
        f"/claims/{claim['id']}/approve",
        json={
            "approved_amount": "5000.00",
            "override_reason": "Cancelled in error",
        },
        headers=auth_headers(test_data["main_admin"]),
    )
    assert forced.status_code == 200, forced.text
    body = forced.json()
    assert body["override_used"] is True
    assert body["decision_coverage"]["covered"] is False
    # The submission snapshot is preserved unchanged.
    assert body["submission_coverage"]["covered"] is True


def test_reject_requires_reason_and_is_final(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = submit(client, headers, case).json()
    client.post(f"/claims/{claim['id']}/review", headers=headers)

    blank = client.post(
        f"/claims/{claim['id']}/reject", json={}, headers=headers
    )
    assert blank.status_code == 422

    rejected = client.post(
        f"/claims/{claim['id']}/reject",
        json={"reason": "Waiting period not served"},
        headers=headers,
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["decision_reason"] == "Waiting period not served"
    assert body["decision_coverage"] is not None

    for path, payload in (
        ("review", None),
        ("approve", {"approved_amount": "1"}),
        ("pay", {"payment_reference": "R"}),
        ("cancel", {}),
    ):
        response = client.post(
            f"/claims/{claim['id']}/{path}",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 409, path

    # A rejected claim does not block a new claim on the case.
    assert submit(client, headers, case).status_code == 201

    assert "claim.rejected" in actions(db, business)


# ============================================================
# CLAIMS: PAYOUT
# ============================================================

def test_pay_without_beneficiaries_records_payment(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case)

    paid = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "EFT-123"},
        headers=headers,
    )

    assert paid.status_code == 200, paid.text
    body = paid.json()
    assert body["status"] == "paid"
    assert body["payment_reference"] == "EFT-123"
    assert body["payout_allocations"] == []
    assert body["paid_by"] == str(test_data["manager"].id)
    assert body["paid_at"] is not None

    assert "claim.paid" in actions(db, business)

    again = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "EFT-124"},
        headers=headers,
    )
    assert again.status_code == 409


def test_payout_splits_by_share_and_sums_exactly(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    add_beneficiary(db, business, membership, "33.33", first_name="A")
    add_beneficiary(db, business, membership, "33.33", first_name="B")
    add_beneficiary(db, business, membership, "33.34", first_name="C")
    case = make_case(db, business, membership)
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case, "100.01")

    paid = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "EFT-1"},
        headers=headers,
    )
    assert paid.status_code == 200, paid.text

    allocations = paid.json()["payout_allocations"]
    assert len(allocations) == 3
    assert sum(Decimal(a["amount"]) for a in allocations) == Decimal(
        "100.01"
    )
    assert [a["name"] for a in allocations] == [
        "A Eficiary",
        "B Eficiary",
        "C Eficiary",
    ]


def test_payout_blocked_unless_shares_total_100(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    add_beneficiary(db, business, membership, 60)
    case = make_case(db, business, membership)
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case)

    blocked = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "EFT-1"},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "100%" in blocked.json()["detail"]

    db.expire_all()
    assert db.query(MembershipClaim).one().status == "approved"

    add_beneficiary(db, business, membership, 40, first_name="Other")

    ok = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "EFT-1"},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text


def test_inactive_beneficiaries_are_excluded_from_payout(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    membership = make_membership(db, business)
    add_beneficiary(db, business, membership, 50, active=False)
    add_beneficiary(db, business, membership, 100, first_name="Only")
    case = make_case(db, business, membership)
    headers = auth_headers(test_data["manager"])

    claim = approved_claim(client, headers, case, "500.00")
    paid = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "R"},
        headers=headers,
    ).json()

    assert len(paid["payout_allocations"]) == 1
    assert paid["payout_allocations"][0]["amount"] == "500.00"


def test_pay_requires_pay_permission(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    manager = test_data["manager"]
    headers = auth_headers(manager)

    claim = approved_claim(client, headers, case)
    set_permission(db, manager.id, "claims.pay", "deny")

    response = client.post(
        f"/claims/{claim['id']}/pay",
        json={"payment_reference": "R"},
        headers=headers,
    )

    assert response.status_code == 403


# ============================================================
# CLAIMS: EDIT / CANCEL / READ
# ============================================================

def test_claim_editable_only_before_decision(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    case = make_case(db, business, make_membership(db, business))
    headers = auth_headers(test_data["manager"])

    claim = submit(client, headers, case).json()

    edit = client.patch(
        f"/claims/{claim['id']}",
        json={"claimed_amount": "11000.00", "notes": "Updated"},
        headers=headers,
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["claimed_amount"] == "11000.00"

    log = (
        db.query(AuditLog)
        .filter(AuditLog.action == "claim.updated")
        .one()
    )
    assert log.details["changes"]["claimed_amount"]["new"] == "11000.00"
    assert log.details["changes"]["notes"]["new"] == "[redacted]"

    client.post(f"/claims/{claim['id']}/review", headers=headers)
    client.post(
        f"/claims/{claim['id']}/approve",
        json={"approved_amount": "11000.00"},
        headers=headers,
    )

    locked = client.patch(
        f"/claims/{claim['id']}",
        json={"claimed_amount": "1.00"},
        headers=headers,
    )
    assert locked.status_code == 409


def test_staff_can_cancel_submitted_but_not_approved_claim(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    staff_headers = auth_headers(test_data["staff"])
    manager_headers = auth_headers(test_data["manager"])

    pending_case = make_case(
        db, business, make_membership(db, business)
    )
    pending = submit(client, staff_headers, pending_case).json()

    cancelled = client.post(
        f"/claims/{pending['id']}/cancel",
        json={"reason": "Raised in error"},
        headers=staff_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    approved_case = make_case(
        db, business, make_membership(db, business)
    )
    approved = approved_claim(client, manager_headers, approved_case)

    refused = client.post(
        f"/claims/{approved['id']}/cancel",
        json={},
        headers=staff_headers,
    )
    assert refused.status_code == 403

    allowed = client.post(
        f"/claims/{approved['id']}/cancel",
        json={"reason": "Family withdrew"},
        headers=manager_headers,
    )
    assert allowed.status_code == 200

    assert "claim.cancelled" in actions(db, business)


def test_list_claims_filters_and_tenant_scope(
    client, test_data, auth_headers, db
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["manager"])

    first_membership = make_membership(db, business)
    first_case = make_case(db, business, first_membership)
    second_case = make_case(db, business, make_membership(db, business))

    first = submit(client, headers, first_case).json()
    submit(client, headers, second_case)
    client.post(f"/claims/{first['id']}/review", headers=headers)

    other_business = test_data["business_b"]
    other_case = make_case(
        db, other_business, make_membership(db, other_business)
    )
    other_claim = submit(
        client,
        auth_headers(test_data["other_business_manager"]),
        other_case,
    ).json()

    everything = client.get("/claims", headers=headers).json()
    assert len(everything) == 2

    reviewing = client.get(
        "/claims?claim_status=under_review", headers=headers
    ).json()
    assert [c["id"] for c in reviewing] == [first["id"]]

    by_membership = client.get(
        f"/claims?membership_id={first_membership.id}", headers=headers
    ).json()
    assert [c["id"] for c in by_membership] == [first["id"]]

    by_case = client.get(
        f"/claims?case_id={second_case.id}", headers=headers
    ).json()
    assert len(by_case) == 1

    assert (
        client.get(
            f"/claims/{other_claim['id']}", headers=headers
        ).status_code
        == 404
    )
    for path, body in (
        ("review", None),
        ("approve", {"approved_amount": "1"}),
        ("reject", {"reason": "x"}),
        ("pay", {"payment_reference": "R"}),
        ("cancel", {}),
    ):
        assert (
            client.post(
                f"/claims/{other_claim['id']}/{path}",
                json=body,
                headers=headers,
            ).status_code
            == 404
        ), path

    assert (
        client.patch(
            f"/claims/{other_claim['id']}",
            json={"notes": "x"},
            headers=headers,
        ).status_code
        == 404
    )
