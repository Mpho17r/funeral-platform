"""
One funeral, start to finish, across every team.

This checks the links between modules: what one team does shows up for the
next team without anyone retyping or phoning. If a step stops reaching the
next screen, this test names the broken link.
"""

from datetime import date

from app.models.notification import Notification
from tests.test_expenses_reconciliation import add_expense
from tests.test_mortuary import (
    event,
    identify,
    make_location,
    prepare_paperwork,
    release,
    take_in,
)
from tests.test_reports import make_case, make_payment
from tests.test_workspace_groups import make_staff

TODAY = date.today()


def get(client, auth_headers, user, path, **params):
    r = client.get(path, params=params, headers=auth_headers(user))
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
    return r.json()


def told(db, user, kind):
    return [
        n.title
        for n in db.query(Notification).filter(
            Notification.user_id == user.id, Notification.kind == kind
        )
    ]


def test_a_funeral_flows_through_every_team(
    client, db, test_data, auth_headers
):
    biz = test_data["business_a"]
    manager = test_data["manager"]
    base = test_data["staff"]
    ops = make_staff(db, base, biz, role="operations", name="Ops")
    morgue = make_staff(db, base, biz, role="mortuary", name="Morgue")
    money = make_staff(db, base, biz, role="finance", name="Money")

    # 1. The family arranges a funeral: a case with a quoted price.
    case = make_case(db, biz, total="5000.00", funeral_date=TODAY)
    case.deceased_full_name = "Nomsa Dlamini"
    db.commit()

    # Operations and the mortuary find it from the shared search box.
    for user in (ops, morgue):
        found = get(client, auth_headers, user, "/search", q="Dlamini")
        assert "cases" in {g["key"] for g in found["groups"]}, \
            "search does not reach the new funeral"

    # 2. The mortuary takes the remains in.
    fridge = make_location(db, biz, "Fridge 1", "fridge", 4)
    r = take_in(client, auth_headers, morgue, case, location_id=str(fridge.id))
    assert r.status_code == 201, r.text

    # -> Operations is told, and the board shows them waiting for ID.
    assert any(
        "taken into the mortuary" in t for t in told(db, ops, "mortuary_update")
    ), "operations was not told the remains arrived"
    board = get(client, auth_headers, morgue, "/mortuary/overview")
    assert board["in_care"] == 1
    assert board["stages"]["awaiting_identification"] == 1

    # 3. Identification, preparation and paperwork -> ready for release.
    identify(client, auth_headers, morgue, case)
    assert event(
        client, auth_headers, morgue, case,
        event_type="prepared", procedure="washed",
    ).status_code == 201
    prepare_paperwork(client, auth_headers, morgue, case)
    board = get(client, auth_headers, morgue, "/mortuary/overview")
    assert board["stages"]["ready_for_release"] == 1
    assert [e["case_number"] for e in board["ready_for_release"]] == [
        case.case_number
    ]

    # 4. Finance takes a deposit and records a cost of this funeral.
    make_payment(db, case, "2000.00", method="cash", on=TODAY)
    spend = add_expense(
        client, auth_headers, money,
        amount="450.00", description="Coffin handles",
        case_id=str(case.id), payment_method="cash",
    )
    assert spend.status_code == 201, spend.text

    desk = get(client, auth_headers, money, "/finance/overview")
    assert desk["collected"]["today"] >= 2000.0, \
        "the deposit did not reach the finance dashboard"
    linked = get(client, auth_headers, money, "/expenses", case_id=str(case.id))
    assert linked["total"] == 450.0

    # 5. End of day: the books say cash in minus cash out.
    day = get(client, auth_headers, money, "/reconciliation")
    cash = next(m for m in day["methods"] if m["payment_method"] == "cash")
    assert cash["receipts"] >= 2000.0
    assert cash["expenses"] == 450.0
    assert cash["expected"] == cash["receipts"] - cash["expenses"]

    done = client.post(
        "/reconciliation",
        json={
            "recon_date": TODAY.isoformat(),
            "payment_method": "cash",
            "counted_amount": str(cash["expected"]),
        },
        headers=auth_headers(money),
    )
    assert done.status_code == 200, done.text
    after = get(client, auth_headers, money, "/reconciliation")
    cash = next(m for m in after["methods"] if m["payment_method"] == "cash")
    assert cash["record"]["variance"] == 0
    assert cash["record"]["needs_review"] is False

    # 6. The family collects: release, and operations is told.
    assert release(client, auth_headers, manager, case).status_code == 200
    board = get(client, auth_headers, morgue, "/mortuary/overview")
    assert board["in_care"] == 0
    assert any(
        "released from the mortuary" in t
        for t in told(db, ops, "mortuary_update")
    ), "operations was not told the remains were released"

    # 7. The owner sees the money from this funeral too.
    owner = get(client, auth_headers, test_data["main_admin"], "/finance/overview")
    assert owner["collected"]["today"] >= 2000.0
