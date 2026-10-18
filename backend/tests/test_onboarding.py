from app.models.member import Member
from app.models.membership_plan import MembershipPlan


def status(client, headers):
    r = client.get("/onboarding/status", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def done(body):
    return {s["key"]: s["done"] for s in body["steps"]}


def test_new_business_has_required_steps_open(client, test_data, auth_headers):
    body = status(client, auth_headers(test_data["main_admin"]))
    d = done(body)
    assert d["plans"] is False and d["members"] is False
    assert body["required_complete"] is False
    assert body["total"] == len(body["steps"])


def test_steps_complete_from_real_data(client, db, test_data, auth_headers):
    h = auth_headers(test_data["main_admin"])
    biz = test_data["business_a"]
    biz.phone = "0110000000"
    db.add(MembershipPlan(
        business_id=biz.id, name="P", monthly_contribution=10, is_active=True
    ))
    db.add(Member(
        business_id=biz.id, member_number="1", first_name="A", last_name="B"
    ))
    db.commit()

    body = status(client, h)
    d = done(body)
    assert d["contact"] and d["plans"] and d["members"]
    assert d["team"]  # fixture already has several users
    assert body["required_complete"] is True


def test_archived_members_and_inactive_plans_do_not_count(
    client, db, test_data, auth_headers
):
    from datetime import datetime, timezone

    h = auth_headers(test_data["main_admin"])
    biz = test_data["business_a"]
    db.add(MembershipPlan(
        business_id=biz.id, name="Old", monthly_contribution=10,
        is_active=False,
    ))
    db.add(Member(
        business_id=biz.id, member_number="1", first_name="A",
        last_name="B", archived_at=datetime.now(timezone.utc),
    ))
    db.commit()

    d = done(status(client, h))
    assert d["plans"] is False and d["members"] is False


def test_other_business_data_is_not_counted(
    client, db, test_data, auth_headers
):
    other = test_data["business_b"]
    db.add(Member(
        business_id=other.id, member_number="1", first_name="A",
        last_name="B",
    ))
    db.commit()

    d = done(status(client, auth_headers(test_data["main_admin"])))
    assert d["members"] is False


# ---- business details -------------------------------------------------

def test_admin_updates_business_details_and_step_completes(
    client, db, test_data, auth_headers
):
    h = auth_headers(test_data["main_admin"])
    biz = test_data["business_a"]

    r = client.patch(
        f"/businesses/{biz.id}/contact",
        headers=h,
        json={
            "name": "  Dlamini Funerals ",
            "phone": " 0115550000 ",
            "email": "",
            "address": "12 Main Rd",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Dlamini Funerals"
    assert body["phone"] == "0115550000"
    assert body["email"] is None

    assert done(status(client, h))["contact"] is True


def test_business_name_cannot_be_blank(client, test_data, auth_headers):
    h = auth_headers(test_data["main_admin"])
    r = client.patch(
        f"/businesses/{test_data['business_a'].id}/contact",
        headers=h,
        json={"name": "   "},
    )
    assert r.status_code == 422


def test_staff_cannot_edit_business_details(client, test_data, auth_headers):
    r = client.patch(
        f"/businesses/{test_data['business_a'].id}/contact",
        headers=auth_headers(test_data["staff"]),
        json={"name": "X"},
    )
    assert r.status_code == 403


def test_cannot_edit_another_business(client, test_data, auth_headers):
    r = client.patch(
        f"/businesses/{test_data['business_b'].id}/contact",
        headers=auth_headers(test_data["main_admin"]),
        json={"name": "X"},
    )
    assert r.status_code in (403, 404)


def test_business_edit_is_audited(client, db, test_data, auth_headers):
    from app.models.audit_log import AuditLog

    client.patch(
        f"/businesses/{test_data['business_a'].id}/contact",
        headers=auth_headers(test_data["main_admin"]),
        json={"name": "New Name", "phone": "0110000000"},
    )
    log = db.query(AuditLog).filter_by(action="business.contact_updated").one()
    assert "phone" in log.details["changes"]
