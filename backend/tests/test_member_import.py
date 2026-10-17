"""Importing an existing member list from a spreadsheet."""

from app.models.audit_log import AuditLog
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan

HEADER = (
    "member_number,first_name,last_name,id_number,date_of_birth,phone,"
    "email,address,join_date,status,plan,membership_number,start_date,"
    "next_due_date\n"
)


def upload(client, headers, text, path="/imports/members/check", **kw):
    return client.post(
        path,
        headers=headers,
        files={"file": ("members.csv", text.encode(), "text/csv")},
        **kw,
    )


def make_plan(db, business_id, name="Family Plan", active=True):
    plan = MembershipPlan(
        business_id=business_id,
        name=name,
        monthly_contribution=100,
        is_active=active,
    )
    db.add(plan)
    db.commit()
    return plan


def admin(test_data, auth_headers):
    return auth_headers(test_data["main_admin"])


def test_template_downloads(client, test_data, auth_headers):
    r = client.get(
        "/imports/members/template", headers=admin(test_data, auth_headers)
    )
    assert r.status_code == 200
    assert r.text.startswith("member_number,first_name,last_name")


def test_check_saves_nothing(client, db, test_data, auth_headers):
    h = admin(test_data, auth_headers)
    r = upload(client, h, HEADER + "M1,Thandi,Nkosi,,,,,,,,,,,\n")
    assert r.status_code == 200
    assert r.json()["ready"] == 1
    assert db.query(Member).count() == 0


def test_import_creates_members_and_policy(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    make_plan(db, test_data["business_a"].id)
    csv = HEADER + (
        "M1,Thandi,Nkosi,,14/03/1985,0821234567,t@example.com,1 Road,"
        "01/02/2023,active,family plan,P1,01/02/2023,01/11/2026\n"
        "M2,Sipho,Dlamini,,,,,,,,,,,\n"
    )
    r = upload(client, h, csv, "/imports/members")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2
    assert body["policies_created"] == 1

    m = db.query(Member).filter_by(member_number="M1").one()
    assert str(m.date_of_birth) == "1985-03-14"
    ms = db.query(Membership).filter_by(membership_number="P1").one()
    assert str(ms.next_due_date) == "2026-11-01"
    assert ms.status == "active"


def test_bad_rows_reported_and_good_rows_still_import(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    csv = HEADER + (
        "M1,Thandi,Nkosi,,,,,,,,,,,\n"
        "M2,,Dlamini,,,,,,,,,,,\n"
        "M3,Zed,Zulu,,,,not-an-email,,,,,,,\n"
        "M4,Amy,Bell,,,,,,,,Nope,P9,,\n"
        "M5,Bad,Date,,,,,,31/02/2020,,,,,\n"
    )
    r = upload(client, h, csv, "/imports/members")
    body = r.json()
    assert body["imported"] == 1
    assert body["skipped"] == 4
    lines = {x["line"]: x for x in body["rows"] if not x["ok"]}
    assert set(lines) == {3, 4, 5, 6}
    assert any("No plan called" in e for e in lines[5]["errors"])
    assert db.query(Member).count() == 1


def test_duplicates_in_file_and_in_database(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    upload(client, h, HEADER + "M1,A,B,,,,,,,,,,,\n", "/imports/members")
    csv = HEADER + "M1,A,B,,,,,,,,,,,\nM2,C,D,,,,,,,,,,,\nM2,E,F,,,,,,,,,,,\n"
    body = upload(client, h, csv).json()
    assert body["ready"] == 1
    assert "already exists" in body["rows"][0]["errors"][0]
    assert "twice" in body["rows"][2]["errors"][0]


def test_inactive_plan_and_missing_policy_number(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    make_plan(db, test_data["business_a"].id, "Old", active=False)
    csv = HEADER + (
        "M1,A,B,,,,,,,,Old,P1,,\n"
        "M2,C,D,,,,,,,,,,2023-01-01,\n"
    )
    rows = upload(client, h, csv).json()["rows"]
    assert "not active" in rows[0]["errors"][0]
    assert any("needs a plan" in e for e in rows[1]["errors"])
    assert any("membership number" in e for e in rows[1]["errors"])


def test_headers_aliases_semicolons_and_bom(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    text = "﻿Member No;Name;Surname;Cell\nM1;Thandi;Nkosi;0821234567\n"
    body = upload(client, h, text, "/imports/members").json()
    assert body["imported"] == 1
    assert db.query(Member).one().phone == "0821234567"


def test_missing_columns_and_empty_files_rejected(
    client, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    r = upload(client, h, "first_name\nA\n")
    assert r.status_code == 400 and "member_number" in r.json()["detail"]
    assert upload(client, h, "").status_code == 400
    assert upload(client, h, HEADER).status_code == 400


def test_unknown_columns_are_reported_not_fatal(
    client, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    body = upload(
        client, h, "member_number,first_name,last_name,favourite\nM1,A,B,x\n"
    ).json()
    assert body["ready"] == 1
    assert body["ignored_columns"] == ["favourite"]


def test_lapsed_member_gets_lapsed_policy(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    make_plan(db, test_data["business_a"].id)
    csv = HEADER + (
        "M1,A,B,,,,,,,lapsed,Family Plan,P1,2022-01-01,2024-01-01\n"
    )
    upload(client, h, csv, "/imports/members")
    ms = db.query(Membership).one()
    assert ms.status == "lapsed" and str(ms.lapsed_at) == "2024-01-01"


def test_staff_cannot_import_manager_can(client, test_data, auth_headers):
    csv = HEADER + "M1,A,B,,,,,,,,,,,\n"
    r = upload(client, auth_headers(test_data["staff"]), csv)
    assert r.status_code == 403
    r = upload(client, auth_headers(test_data["manager"]), csv)
    assert r.status_code == 200


def test_import_is_audited_without_personal_details(
    client, db, test_data, auth_headers
):
    h = admin(test_data, auth_headers)
    upload(
        client, h, HEADER + "M1,Thandi,Nkosi,,,0821234567,,,,,,,,\n",
        "/imports/members",
    )
    log = db.query(AuditLog).filter_by(action="import.members").one()
    assert log.details["members_created"] == 1
    assert "Thandi" not in str(log.details) + str(log.notes)
    assert "0821234567" not in str(log.details)
