"""Importing funerals already in progress from the old system."""

from datetime import date, timedelta

from app.models.audit_log import AuditLog
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_plan import MembershipPlan

HEADER = (
    "case_number,deceased_full_name,date_of_birth,date_of_death,"
    "funeral_date,funeral_venue,next_of_kin_name,next_of_kin_phone,"
    "status,membership_number,notes\n"
)


def upload(client, headers, text, path="/imports/cases/check"):
    return client.post(
        path,
        headers=headers,
        files={"file": ("cases.csv", text.encode(), "text/csv")},
    )


def admin(test_data, auth_headers):
    return auth_headers(test_data["main_admin"])


def make_policy(db, test_data, number="P1"):
    biz = test_data["business_a"]
    plan = MembershipPlan(
        business_id=biz.id, name="Plan", monthly_contribution=100,
        is_active=True,
    )
    member = Member(
        business_id=biz.id, member_number="M" + number,
        first_name="A", last_name="B",
    )
    db.add_all([plan, member])
    db.flush()
    ms = Membership(
        business_id=biz.id, member_id=member.id, plan_id=plan.id,
        membership_number=number, start_date=date(2024, 1, 1),
    )
    db.add(ms)
    db.commit()
    return ms


def test_template(client, test_data, auth_headers):
    r = client.get("/imports/cases/template", headers=admin(test_data, auth_headers))
    assert r.status_code == 200 and r.text.startswith("case_number")


def test_check_saves_nothing(client, db, test_data, auth_headers):
    body = upload(
        client, admin(test_data, auth_headers),
        HEADER + "C1,Themba Nkosi,,2026-10-01,2026-10-10,,,,,,\n",
    ).json()
    assert body["ready"] == 1
    assert db.query(FuneralCase).count() == 0


def test_import_saves_cases_with_status_and_policy(
    client, db, test_data, auth_headers
):
    ms = make_policy(db, test_data)
    csv = HEADER + (
        "C1,Themba Nkosi,1948-06-02,10/10/2026,18/10/2026,Westpark,"
        "Thandi,0821234567,In Progress,P1,note\n"
        "C2,Anna Venter,,,,,,,,,\n"
    )
    r = upload(client, admin(test_data, auth_headers), csv, "/imports/cases")
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2

    c1 = db.query(FuneralCase).filter_by(case_number="C1").one()
    assert c1.status == "in_progress" and c1.membership_id == ms.id
    assert str(c1.date_of_death) == "2026-10-10"
    assert c1.is_archived is False
    c2 = db.query(FuneralCase).filter_by(case_number="C2").one()
    assert c2.status == "open"


def test_row_problems_are_reported(client, db, test_data, auth_headers):
    tomorrow = date.today() + timedelta(days=1)
    csv = HEADER + (
        ",NoNumber,,,,,,,,,\n"
        "C2,,,,,,,,,,\n"
        f"C3,Future,,{tomorrow},,,,,,,\n"
        "C4,Backwards,2000-01-01,1990-01-01,,,,,,,\n"
        "C5,EarlyBurial,,2026-10-10,2026-10-01,,,,,,\n"
        "C6,BadStatus,,,,,,,pending,,\n"
        "C7,NoPolicy,,,,,,,,ZZZ,\n"
        "C8,BadDate,,31/02/2026,,,,,,,\n"
        "C9,Fine,,,,,,,,,\n"
    )
    rows = upload(client, admin(test_data, auth_headers), csv).json()["rows"]
    assert [r["ok"] for r in rows] == [False] * 8 + [True]
    assert "future" in rows[2]["errors"][0]
    assert "after the date of death" in rows[3]["errors"][0]
    assert "before the date of death" in rows[4]["errors"][0]
    assert "Unknown status" in rows[5]["errors"][0]
    assert "No membership numbered" in rows[6]["errors"][0]


def test_duplicates_in_file_and_database(client, db, test_data, auth_headers):
    h = admin(test_data, auth_headers)
    upload(client, h, HEADER + "C1,A,,,,,,,,,\n", "/imports/cases")
    csv = HEADER + "C1,A,,,,,,,,,\nC2,B,,,,,,,,,\nC2,C,,,,,,,,,\n"
    rows = upload(client, h, csv).json()["rows"]
    assert "already exists" in rows[0]["errors"][0]
    assert rows[1]["ok"] and "twice" in rows[2]["errors"][0]


def test_aliases_and_semicolons(client, db, test_data, auth_headers):
    text = "Case No;Deceased;DOD;Burial Date;Cemetery\nC1;Lerato M;2026-10-01;2026-10-09;Avalon\n"
    r = upload(client, admin(test_data, auth_headers), text, "/imports/cases")
    assert r.json()["imported"] == 1
    c = db.query(FuneralCase).one()
    assert c.funeral_venue == "Avalon" and str(c.funeral_date) == "2026-10-09"


def test_bad_files(client, test_data, auth_headers):
    h = admin(test_data, auth_headers)
    assert upload(client, h, "deceased\nx\n").status_code == 400
    assert upload(client, h, HEADER).status_code == 400
    assert upload(client, h, "").status_code == 400


def test_other_business_policy_not_linked(client, db, test_data, auth_headers):
    make_policy(db, test_data)
    rows = upload(
        client, auth_headers(test_data["other_business_manager"]),
        HEADER + "C1,A,,,,,,,,P1,\n",
    ).json()["rows"]
    assert "No membership numbered" in rows[0]["errors"][0]


def test_permission_and_audit(client, db, test_data, auth_headers):
    csv = HEADER + "C1,Themba,,,,,,,,,\n"
    assert upload(client, auth_headers(test_data["staff"]), csv).status_code == 403
    upload(client, auth_headers(test_data["manager"]), csv, "/imports/cases")
    log = db.query(AuditLog).filter_by(action="import.cases").one()
    assert log.details["cases_created"] == 1
    assert "Themba" not in str(log.details) + str(log.notes)
