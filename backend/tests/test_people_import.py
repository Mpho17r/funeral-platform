"""Importing covered dependents and beneficiaries."""

from datetime import date
from decimal import Decimal

from app.models.audit_log import AuditLog
from app.models.covered_dependent import CoveredDependent
from app.models.member import Member
from app.models.membership import Membership
from app.models.membership_beneficiary import MembershipBeneficiary
from app.models.membership_plan import MembershipPlan

DEP = (
    "membership_number,first_name,last_name,relationship,id_number,"
    "date_of_birth,phone,status,cover_start_date,cover_end_date\n"
)
BEN = (
    "membership_number,first_name,last_name,relationship,id_number,phone,"
    "email,share_percent,notes\n"
)


def upload(client, headers, kind, text, mode=""):
    return client.post(
        f"/imports/{kind}{mode}",
        headers=headers,
        files={"file": ("p.csv", text.encode(), "text/csv")},
    )


def check(client, h, kind, text):
    return upload(client, h, kind, text, "/check")


def setup_policy(db, test_data, number="P1"):
    biz = test_data["business_a"]
    plan = MembershipPlan(
        business_id=biz.id, name="Plan", monthly_contribution=Decimal("100"),
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
        membership_number=number, start_date=date(2025, 1, 1),
        status="active",
    )
    db.add(ms)
    db.commit()
    return ms


def admin(test_data, auth_headers):
    return auth_headers(test_data["main_admin"])


# ---- dependents ---------------------------------------------------------

def test_templates_download(client, test_data, auth_headers):
    h = admin(test_data, auth_headers)
    for kind in ("dependents", "beneficiaries"):
        r = client.get(f"/imports/{kind}/template", headers=h)
        assert r.status_code == 200 and r.text.startswith("membership_number")


def test_dependents_import_with_words_and_defaults(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = DEP + (
        "P1,Sipho,Nkosi,Son,,09/04/2012,,,,\n"
        "P1,Mary,Nkosi,wife,,,,active,2025-03-01,\n"
    )
    assert check(client, h, "dependents", csv).json()["ready"] == 2
    assert db.query(CoveredDependent).count() == 0

    body = upload(client, h, "dependents", csv).json()
    assert body["imported"] == 2

    kid = db.query(CoveredDependent).filter_by(first_name="Sipho").one()
    assert kid.relationship == "child"
    assert kid.cover_start_date == date(2025, 1, 1)  # the policy start
    assert kid.status == "active"
    wife = db.query(CoveredDependent).filter_by(first_name="Mary").one()
    assert wife.relationship == "spouse"
    assert any("policy start" in w for w in body["rows"][0]["warnings"])


def test_dependent_problems_reported(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = DEP + (
        "NOPE,A,B,child,,,,,,\n"
        "P1,A,B,cousin,,,,,,\n"
        "P1,A,B,child,1234567890123,,,,,\n"
        "P1,A,B,child,,2999-01-01,,,,\n"
        "P1,A,B,child,,,,missing,,\n"
        "P1,A,B,child,,,,,2025-05-01,2025-04-01\n"
        "P1,,B,child,,,,,,\n"
    )
    rows = check(client, h, "dependents", csv).json()["rows"]
    assert len(rows) == 7 and not any(r["ok"] for r in rows)
    assert "No membership numbered" in rows[0]["errors"][0]
    assert "Unknown relationship" in rows[1]["errors"][0]
    assert "ID number" in rows[2]["errors"][0]
    assert "future" in rows[3]["errors"][0]
    assert "Unknown status" in rows[4]["errors"][0]
    assert "before it starts" in rows[5]["errors"][0] or "ends before" in rows[5]["errors"][0]


def test_dependent_duplicates_file_and_database(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = DEP + (
        "P1,Sipho,Nkosi,child,,2012-04-09,,,,\n"
        "P1,sipho,NKOSI,child,,2012-04-09,,,,\n"
    )
    rows = check(client, h, "dependents", csv).json()["rows"]
    assert [r["ok"] for r in rows] == [True, False]

    upload(client, h, "dependents", csv)
    again = upload(client, h, "dependents", csv).json()
    assert again["imported"] == 0 and db.query(CoveredDependent).count() == 1


# ---- beneficiaries ------------------------------------------------------

def test_beneficiaries_import_and_share_total_note(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = BEN + (
        "P1,Thandi,Nkosi,spouse,,0821234567,t@example.com,60%,\n"
        "P1,Sipho,Nkosi,child,,,,30,\n"
    )
    body = upload(client, h, "beneficiaries", csv).json()
    assert body["imported"] == 2
    assert any("90" in n and "100%" in n for n in body["policy_notes"])

    rows = db.query(MembershipBeneficiary).all()
    assert {r.share_percent for r in rows} == {Decimal("60.00"), Decimal("30.00")}
    assert all(r.is_active for r in rows)


def test_beneficiary_shares_cannot_exceed_100_including_existing(
    client, db, test_data, auth_headers
):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    upload(client, h, "beneficiaries", BEN + "P1,A,B,spouse,,,,70,\n")
    csv = BEN + "P1,C,D,child,,,,20,\nP1,E,F,child,,,,20,\n"
    body = upload(client, h, "beneficiaries", csv).json()
    assert body["imported"] == 1 and body["skipped"] == 1
    assert "more than 100" in body["rows"][1]["errors"][0]


def test_beneficiary_bad_values(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    csv = BEN + (
        "P1,A,B,spouse,,,,abc,\n"
        "P1,A,B,spouse,,,,0,\n"
        "P1,A,B,spouse,,,,101,\n"
        "P1,A,B,spouse,,,,50,\n"
        "P1,A,B,spouse,,,not-email,50,\n"
        "P1,A,B,spouse,,,,,\n"
    )
    rows = check(client, h, "beneficiaries", csv).json()["rows"]
    assert [r["ok"] for r in rows] == [False, False, False, True, False, False]


def test_bad_files_and_permissions(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    assert check(client, h, "dependents", "first_name\nA\n").status_code == 400
    assert check(client, h, "beneficiaries", DEP + "P1,A,B,child,,,,,,\n").status_code == 400
    csv = DEP + "P1,A,B,child,,,,,,\n"
    assert check(
        client, auth_headers(test_data["staff"]), "dependents", csv
    ).status_code == 403


def test_other_business_policy_not_matched(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    rows = check(
        client, auth_headers(test_data["other_business_manager"]),
        "dependents", DEP + "P1,A,B,child,,,,,,\n",
    ).json()["rows"]
    assert "No membership numbered" in rows[0]["errors"][0]


def test_audit_entries(client, db, test_data, auth_headers):
    setup_policy(db, test_data)
    h = admin(test_data, auth_headers)
    upload(client, h, "dependents", DEP + "P1,Sipho,Nkosi,child,,,,,,\n")
    upload(client, h, "beneficiaries", BEN + "P1,Thandi,Nkosi,spouse,,,,100,\n")
    for action in ("import.dependents", "import.beneficiaries"):
        log = db.query(AuditLog).filter_by(action=action).one()
        assert log.details["people_created"] == 1
        assert "Nkosi" not in str(log.details) + str(log.notes)
