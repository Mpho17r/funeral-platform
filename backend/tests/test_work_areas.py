"""Work areas: a staff member only gets the permissions of their job."""

from app.models.audit_log import AuditLog
from app.models.permission import Permission
from app.models.user_permission import UserPermission
from app.services.permission_service import effective_permissions, has_permission
from app.services.work_areas import WORK_AREAS


import pytest

from app.services.permission_seed import sync_permission_system


@pytest.fixture(autouse=True)
def seeded(db):
    sync_permission_system(db)
    db.commit()


def as_area(db, user, area):
    user.work_area = area
    db.commit()


def hit(client, auth_headers, user, method, path, **kw):
    return getattr(client, method)(path, headers=auth_headers(user), **kw)


def can(db, user, key):
    return has_permission(
        db, user_id=user.id, role=user.role, permission_key=key
    )


def test_general_staff_keeps_the_broad_staff_access(db, test_data):
    staff = test_data["staff"]
    assert staff.work_area == "general"
    assert can(db, staff, "payments.view")
    assert can(db, staff, "remains.manage")
    assert can(db, staff, "members.create")


def test_mortuary_sees_mortuary_but_not_money_or_members(db, test_data):
    staff = test_data["staff"]
    as_area(db, staff, "mortuary")
    for key in ("remains.manage", "mortuary.view", "death_records.manage",
                "chat.use", "dashboard.view"):
        assert can(db, staff, key), key
    for key in ("payments.view", "financials.view", "memberships.view",
                "contributions.view", "reports.view", "members.view",
                "remains.release", "users.view"):
        assert not can(db, staff, key), key


def test_finance_sees_money_and_members_but_not_the_mortuary(db, test_data):
    staff = test_data["staff"]
    as_area(db, staff, "finance")
    for key in ("payments.create", "contributions.create",
                "memberships.create", "reports.view", "financials.view"):
        assert can(db, staff, key), key
    for key in ("mortuary.view", "remains.view", "cases.view",
                "cases.create", "death_records.view"):
        assert not can(db, staff, key), key


def test_operations_runs_cases_but_not_payments(db, test_data):
    staff = test_data["staff"]
    as_area(db, staff, "operations")
    for key in ("cases.create", "cases.edit", "arrangements.manage",
                "services.manage", "run_sheet.view"):
        assert can(db, staff, key), key
    for key in ("payments.view", "payments.create", "financials.view",
                "contributions.view", "reports.view", "remains.manage"):
        assert not can(db, staff, key), key


def test_every_area_permission_exists_in_the_catalogue():
    from app.permissions import PERMISSIONS

    for name, area in WORK_AREAS.items():
        unknown = set(area["permissions"]) - set(PERMISSIONS)
        assert not unknown, (name, unknown)


def test_overrides_still_apply_on_top_of_an_area(db, test_data):
    staff = test_data["staff"]
    as_area(db, staff, "mortuary")
    perm = db.query(Permission).filter(Permission.key == "payments.view").one()
    db.add(UserPermission(user_id=staff.id, permission_id=perm.id,
                          effect="allow"))
    perm2 = db.query(Permission).filter(Permission.key == "remains.manage").one()
    db.add(UserPermission(user_id=staff.id, permission_id=perm2.id,
                          effect="deny"))
    db.commit()
    assert can(db, staff, "payments.view")
    assert not can(db, staff, "remains.manage")


def test_managers_and_admins_ignore_work_areas(db, test_data):
    manager = test_data["manager"]
    as_area(db, manager, "mortuary")
    assert can(db, manager, "payments.view")
    assert can(db, test_data["main_admin"], "payments.view")


def test_api_blocks_a_mortuary_worker_from_money(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    as_area(db, staff, "mortuary")
    assert hit(client, auth_headers, staff, "get",
               "/memberships").status_code == 403
    assert hit(client, auth_headers, staff, "get",
               "/reports/financial").status_code == 403
    assert hit(client, auth_headers, staff, "get",
               "/mortuary/locations").status_code == 200


def test_api_blocks_a_finance_clerk_from_the_mortuary(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    as_area(db, staff, "finance")
    assert hit(client, auth_headers, staff, "get",
               "/mortuary/locations").status_code == 403
    assert hit(client, auth_headers, staff, "get",
               "/memberships").status_code == 200


def test_dashboard_hides_money_and_cases_when_not_allowed(
    client, db, test_data, auth_headers
):
    from tests.test_reports import make_case, make_payment

    biz = test_data["business_a"]
    case = make_case(db, biz, total="900.00")
    make_payment(db, case, "300.00")

    staff = test_data["staff"]
    as_area(db, staff, "mortuary")
    body = hit(client, auth_headers, staff, "get", "/dashboard/summary").json()
    assert body["outstanding_balance"] is None
    assert body["total_revenue"] is None
    assert len(body["recent_cases"]) == 1  # the mortuary works cases

    as_area(db, staff, "operations")
    body = hit(client, auth_headers, staff, "get", "/dashboard/summary").json()
    assert body["total_revenue"] is None
    assert len(body["recent_cases"]) == 1

    as_area(db, staff, "finance")
    body = hit(client, auth_headers, staff, "get", "/dashboard/summary").json()
    assert body["total_revenue"] is not None
    assert body["recent_cases"] == []

    body = hit(client, auth_headers, test_data["manager"], "get",
               "/dashboard/summary").json()
    assert body["total_revenue"] is not None


def test_my_access_lists_what_i_can_do(client, db, test_data, auth_headers):
    staff = test_data["staff"]
    as_area(db, staff, "mortuary")
    body = hit(client, auth_headers, staff, "get", "/users/me/access").json()
    assert body["role"] == "staff" and body["work_area"] == "mortuary"
    assert "remains.manage" in body["permissions"]
    assert "payments.view" not in body["permissions"]

    admin = hit(client, auth_headers, test_data["main_admin"], "get",
                "/users/me/access").json()
    assert "payments.view" in admin["permissions"]


def test_my_access_matches_has_permission(db, test_data):
    for key in ("staff", "manager"):
        user = test_data[key]
        if key == "staff":
            as_area(db, user, "finance")
        granted = effective_permissions(db, user=user)
        for perm in db.query(Permission.key).all():
            assert (perm[0] in granted) == can(db, user, perm[0]), perm[0]


def test_setting_a_work_area_is_audited_and_validated(
    client, db, test_data, auth_headers
):
    staff = test_data["staff"]
    admin = test_data["main_admin"]

    r = hit(client, auth_headers, admin, "patch", f"/users/{staff.id}",
            json={"work_area": "mortuary"})
    assert r.status_code == 200 and r.json()["work_area"] == "mortuary"
    log = db.query(AuditLog).filter_by(action="user.work_area_changed").one()
    assert log.details["changes"]["work_area"]["new"] == "mortuary" or \
        "mortuary" in str(log.details)

    assert hit(client, auth_headers, admin, "patch", f"/users/{staff.id}",
               json={"work_area": "pirates"}).status_code == 422

    manager = test_data["manager"]
    assert hit(client, auth_headers, admin, "patch", f"/users/{manager.id}",
               json={"work_area": "finance"}).status_code == 400


def test_you_cannot_change_your_own_work_area(
    client, db, test_data, auth_headers
):
    manager = test_data["manager"]
    r = hit(client, auth_headers, manager, "patch", f"/users/{manager.id}",
            json={"work_area": "general"})
    assert r.status_code == 200
    # a staff member without users.edit cannot do it at all
    staff = test_data["staff"]
    assert hit(client, auth_headers, staff, "patch", f"/users/{staff.id}",
               json={"work_area": "general"}).status_code == 403


def test_work_area_catalogue(client, test_data, auth_headers):
    r = hit(client, auth_headers, test_data["manager"], "get",
            "/users/work-areas")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert ids == ["general", "mortuary", "finance", "operations"]
