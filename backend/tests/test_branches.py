import uuid

from datetime import date

from app.models.audit_log import AuditLog
from app.models.branch import Branch
from app.models.funeral_case import FuneralCase
from app.models.member import Member
from app.models.permission import Permission
from app.models.resource import Resource
from app.models.user import User
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


def make_branch(
    db,
    business,
    name="Soweto",
    code="SWT",
    *,
    main=False,
    active=True,
):
    branch = Branch(
        business_id=business.id,
        name=name,
        code=code,
        is_main=main,
        is_active=active,
    )
    db.add(branch)
    db.commit()

    return branch


def make_case(
    db,
    business,
    branch=None,
    *,
    status="open",
    archived=False,
):
    case = FuneralCase(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        case_number=f"BR-{uuid.uuid4().hex[:8].upper()}",
        deceased_full_name="Private Name",
        date_of_death=date(2026, 10, 1),
        status=status,
        is_archived=archived,
    )
    db.add(case)
    db.commit()

    return case


def make_member(db, business, branch=None):
    member = Member(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        member_number=f"M-{uuid.uuid4().hex[:8].upper()}",
        first_name="Branch",
        last_name="Member",
        join_date=date(2026, 1, 1),
        status="active",
    )
    db.add(member)
    db.commit()

    return member


def make_resource(db, business, branch=None, *, active=True):
    resource = Resource(
        business_id=business.id,
        branch_id=branch.id if branch else None,
        resource_type="vehicle",
        name=f"Hearse {uuid.uuid4().hex[:6]}",
        is_active=active,
    )
    db.add(resource)
    db.commit()

    return resource


def put_user_in(db, user, branch):
    user.branch_id = branch.id
    db.commit()


def audit(db, entity_id, action):
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_id == entity_id,
            AuditLog.action == action,
        )
        .all()
    )


def post_branch(client, headers, name="Soweto", code="swt", **extra):
    return client.post(
        "/branches",
        json={"name": name, "code": code, **extra},
        headers=headers,
    )


# ============================================================
# REGISTRATION
# ============================================================

def test_registration_creates_a_main_branch_for_the_new_admin(
    client, db,
):
    response = client.post(
        "/auth/register",
        json={
            "business_name": "Fresh Funerals",
            "full_name": "Owner Person",
            "email": "owner-branch@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 201, response.text

    admin = (
        db.query(User)
        .filter(User.email == "owner-branch@example.com")
        .one()
    )

    branches = (
        db.query(Branch)
        .filter(Branch.business_id == admin.business_id)
        .all()
    )

    assert len(branches) == 1
    assert branches[0].is_main is True
    assert branches[0].is_active is True
    assert admin.branch_id == branches[0].id


# ============================================================
# CREATE AND READ
# ============================================================

def test_main_admin_creates_branch_with_clean_code_and_audit(
    client, db, test_data, auth_headers,
):
    admin = test_data["main_admin"]

    response = post_branch(
        client,
        auth_headers(admin),
        name="  Soweto Branch ",
        code=" swt1 ",
        phone="0110000000",
    )

    assert response.status_code == 201, response.text

    branch = response.json()

    assert branch["name"] == "Soweto Branch"
    assert branch["code"] == "SWT1"
    assert branch["is_active"] is True
    assert branch["business_id"] == str(test_data["business_a"].id)

    entries = audit(db, uuid.UUID(branch["id"]), "branch.created")

    assert len(entries) == 1
    assert entries[0].user_id == admin.id
    assert entries[0].business_id == test_data["business_a"].id


def test_first_branch_of_a_business_without_one_becomes_main(
    client, db, test_data, auth_headers,
):
    response = post_branch(
        client, auth_headers(test_data["main_admin"])
    )

    assert response.json()["is_main"] is True

    second = post_branch(
        client,
        auth_headers(test_data["main_admin"]),
        name="Orlando",
        code="ORL",
    )

    assert second.json()["is_main"] is False


def test_invalid_codes_are_rejected(
    client, db, test_data, auth_headers,
):
    headers = auth_headers(test_data["main_admin"])

    for bad in ("A", "has space", "TOOLONGCODE1", "AB-1", ""):
        response = post_branch(client, headers, code=bad)

        assert response.status_code == 422, bad

    assert db.query(Branch).count() == 0


def test_duplicate_code_and_name_are_rejected_per_business(
    client, db, test_data, auth_headers,
):
    business_a = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])
    make_branch(db, business_a, "Soweto", "SWT", main=True)

    same_code = post_branch(client, headers, name="Other", code="swt")
    same_name = post_branch(
        client, headers, name="soweto", code="OTH"
    )

    assert same_code.status_code == 409
    assert "code" in same_code.json()["detail"]
    assert same_name.status_code == 409
    assert "name" in same_name.json()["detail"]

    # Another business may reuse both.
    other = post_branch(
        client,
        auth_headers(test_data["other_business_manager"]),
        name="Soweto",
        code="SWT",
    )
    # A manager lacks branches.manage, so this proves the rule is
    # per business only once an admin of that business does it.
    assert other.status_code == 403


def test_branches_are_listed_main_first_and_hide_inactive(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    make_branch(db, business, "Zeta", "ZET")
    make_branch(db, business, "Main Office", "MAIN", main=True)
    make_branch(db, business, "Closed", "CLS", active=False)

    headers = auth_headers(test_data["staff"])

    default = client.get("/branches", headers=headers).json()
    everything = client.get(
        "/branches?include_inactive=true", headers=headers
    ).json()

    assert [b["name"] for b in default] == ["Main Office", "Zeta"]
    assert {b["name"] for b in everything} == {
        "Main Office",
        "Zeta",
        "Closed",
    }


# ============================================================
# UPDATE
# ============================================================

def test_update_audits_exact_changes_and_redacts_contact_details(
    client, db, test_data, auth_headers,
):
    branch = make_branch(
        db, test_data["business_a"], main=True
    )

    response = client.patch(
        f"/branches/{branch.id}",
        json={
            "name": "Soweto Central",
            "phone": "0119999999",
            "address": "12 Vilakazi Street",
        },
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text

    changes = audit(db, branch.id, "branch.updated")[0].details[
        "changes"
    ]

    assert set(changes) == {"name", "phone", "address"}
    assert changes["name"] == {
        "old": "Soweto",
        "new": "Soweto Central",
    }
    assert changes["phone"]["new"] == "[redacted]"
    assert changes["address"]["new"] == "[redacted]"

    text = str(audit(db, branch.id, "branch.updated")[0].details)
    assert "0119999999" not in text
    assert "Vilakazi" not in text


def test_unchanged_update_writes_no_audit_and_nulls_are_refused(
    client, db, test_data, auth_headers,
):
    branch = make_branch(db, test_data["business_a"], main=True)
    headers = auth_headers(test_data["main_admin"])

    same = client.patch(
        f"/branches/{branch.id}",
        json={"name": "Soweto"},
        headers=headers,
    )
    null_name = client.patch(
        f"/branches/{branch.id}",
        json={"name": None},
        headers=headers,
    )
    unknown = client.patch(
        f"/branches/{branch.id}",
        json={"is_main": True},
        headers=headers,
    )

    assert same.status_code == 200
    assert audit(db, branch.id, "branch.updated") == []
    assert null_name.status_code == 422
    # Main and active status only change through their own actions.
    assert unknown.status_code == 422


# ============================================================
# DEACTIVATE, REACTIVATE, MAIN BRANCH
# ============================================================

def test_main_branch_cannot_be_deactivated(
    client, db, test_data, auth_headers,
):
    main = make_branch(db, test_data["business_a"], main=True)

    response = client.post(
        f"/branches/{main.id}/deactivate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 409
    assert "main branch" in response.json()["detail"]


def test_branch_with_live_cases_cannot_be_deactivated(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    make_branch(db, business, "Main", "MAIN", main=True)
    branch = make_branch(db, business)
    make_case(db, business, branch, status="open")
    make_case(db, business, branch, status="in_progress")
    make_case(db, business, branch, status="closed")
    make_case(db, business, branch, status="open", archived=True)

    response = client.post(
        f"/branches/{branch.id}/deactivate",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 409
    assert "2 live cases" in response.json()["detail"]

    db.refresh(branch)
    assert branch.is_active is True


def test_branch_can_be_deactivated_and_reactivated_with_audit(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])
    make_branch(db, business, "Main", "MAIN", main=True)
    branch = make_branch(db, business)
    make_case(db, business, branch, status="closed")

    off = client.post(
        f"/branches/{branch.id}/deactivate", headers=headers
    )
    again = client.post(
        f"/branches/{branch.id}/deactivate", headers=headers
    )

    assert off.status_code == 200
    assert off.json()["is_active"] is False
    assert again.status_code == 409

    on = client.post(
        f"/branches/{branch.id}/reactivate", headers=headers
    )
    twice = client.post(
        f"/branches/{branch.id}/reactivate", headers=headers
    )

    assert on.json()["is_active"] is True
    assert twice.status_code == 409

    for action in ("branch.deactivated", "branch.reactivated"):
        assert len(audit(db, branch.id, action)) == 1


def test_make_main_moves_the_flag_and_keeps_exactly_one_main(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])
    old_main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business)

    response = client.post(
        f"/branches/{other.id}/make-main", headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_main"] is True

    db.expire_all()

    mains = (
        db.query(Branch)
        .filter(
            Branch.business_id == business.id,
            Branch.is_main.is_(True),
        )
        .all()
    )

    assert [b.id for b in mains] == [other.id]
    assert db.get(Branch, old_main.id).is_main is False

    entry = audit(db, other.id, "branch.made_main")[0]
    assert entry.details["previous_main_branch_id"] == str(old_main.id)

    # The former main branch can now be deactivated.
    assert client.post(
        f"/branches/{old_main.id}/deactivate", headers=headers
    ).status_code == 200


def test_make_main_rules(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    headers = auth_headers(test_data["main_admin"])
    main = make_branch(db, business, "Main", "MAIN", main=True)
    closed = make_branch(db, business, "Closed", "CLS", active=False)

    assert client.post(
        f"/branches/{main.id}/make-main", headers=headers
    ).status_code == 409
    assert client.post(
        f"/branches/{closed.id}/make-main", headers=headers
    ).status_code == 409


# ============================================================
# SUMMARY
# ============================================================

def test_branch_summary_counts_only_that_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business)

    put_user_in(db, test_data["manager"], other)
    put_user_in(db, test_data["staff"], other)
    test_data["staff"].is_active = False
    db.commit()

    make_case(db, business, other, status="open")
    make_case(db, business, other, status="closed")
    make_case(db, business, main, status="open")
    make_member(db, business, other)
    make_resource(db, business, other)
    make_resource(db, business, other, active=False)

    response = client.get(
        f"/branches/{other.id}/summary",
        headers=auth_headers(test_data["main_admin"]),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "branch_id": str(other.id),
        "active_staff": 1,
        "active_resources": 1,
        "members": 1,
        "live_cases": 1,
        "total_cases": 2,
    }


# ============================================================
# PERMISSIONS AND TENANT ISOLATION
# ============================================================

def test_branch_management_needs_manage_permission(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    branch = make_branch(db, business, main=True)
    other = make_branch(db, business, "Other", "OTH")

    for user in (test_data["manager"], test_data["staff"]):
        headers = auth_headers(user)

        assert client.get("/branches", headers=headers).status_code == 200

        denied = [
            post_branch(client, headers, name="New", code="NEW"),
            client.patch(
                f"/branches/{branch.id}",
                json={"name": "X"},
                headers=headers,
            ),
            client.post(
                f"/branches/{other.id}/deactivate", headers=headers
            ),
            client.post(
                f"/branches/{other.id}/make-main", headers=headers
            ),
        ]

        for response in denied:
            assert response.status_code == 403, response.text


def test_denying_view_hides_branches(
    client, db, test_data, auth_headers,
):
    make_branch(db, test_data["business_a"], main=True)
    staff = test_data["staff"]

    set_permission(db, staff.id, "branches.view", "deny")

    assert client.get(
        "/branches", headers=auth_headers(staff)
    ).status_code == 403


def test_other_business_cannot_see_or_change_a_branch(
    client, db, test_data, auth_headers,
):
    branch = make_branch(db, test_data["business_a"], main=True)
    outsider = auth_headers(test_data["other_business_manager"])

    responses = [
        client.get(f"/branches/{branch.id}", headers=outsider),
        client.get(f"/branches/{branch.id}/summary", headers=outsider),
    ]

    for response in responses:
        assert response.status_code == 404, response.text

    assert client.get("/branches", headers=outsider).json() == []

    # Admin rights in business B never reach business A's branches.
    other_admin = User(
        business_id=test_data["business_b"].id,
        full_name="Other Admin",
        email=f"other-admin-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=test_data["main_admin"].password_hash,
        role="main_admin",
        is_active=True,
    )
    db.add(other_admin)
    db.commit()

    admin_headers = auth_headers(other_admin)

    for response in (
        client.patch(
            f"/branches/{branch.id}",
            json={"name": "Hijacked"},
            headers=admin_headers,
        ),
        client.post(
            f"/branches/{branch.id}/deactivate", headers=admin_headers
        ),
        client.post(
            f"/branches/{branch.id}/make-main", headers=admin_headers
        ),
    ):
        assert response.status_code == 404, response.text

    db.refresh(branch)
    assert branch.name == "Soweto"


# ============================================================
# NEW RECORDS GET A BRANCH
# ============================================================

def create_each(client, headers, branch_id=None):
    """Create one case, member, resource and user. Returns the
    responses in that order."""

    extra = {"branch_id": str(branch_id)} if branch_id else {}
    suffix = uuid.uuid4().hex[:8]

    return (
        client.post(
            "/cases",
            json={
                "case_number": f"NEW-{suffix}",
                "deceased_full_name": "New Person",
                **extra,
            },
            headers=headers,
        ),
        client.post(
            "/members",
            json={
                "member_number": f"NM-{suffix}",
                "first_name": "New",
                "last_name": "Member",
                **extra,
            },
            headers=headers,
        ),
        client.post(
            "/resources",
            json={
                "resource_type": "vehicle",
                "name": f"Van {suffix}",
                **extra,
            },
            headers=headers,
        ),
        client.post(
            "/users",
            json={
                "full_name": "New Staff",
                "email": f"new-{suffix}@example.com",
                "password": "TestPassword123!",
                "role": "staff",
                **extra,
            },
            headers=headers,
        ),
    )


def test_new_records_default_to_the_creators_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    manager = test_data["manager"]
    make_branch(db, business, "Main", "MAIN", main=True)
    mine = make_branch(db, business)
    put_user_in(db, manager, mine)

    responses = create_each(client, auth_headers(manager))

    for response in responses:
        assert response.status_code == 201, response.text
        assert response.json()["branch_id"] == str(mine.id)


def test_creator_without_a_branch_falls_back_to_the_main_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    make_branch(db, business)

    # The test manager has no branch of their own.
    for response in create_each(client, auth_headers(test_data["manager"])):
        assert response.status_code == 201, response.text
        assert response.json()["branch_id"] == str(main.id)


def test_creator_in_an_inactive_branch_falls_back_to_main(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    closed = make_branch(db, business, "Closed", "CLS", active=False)
    put_user_in(db, test_data["manager"], closed)

    cases, *_ = create_each(client, auth_headers(test_data["manager"]))

    assert cases.json()["branch_id"] == str(main.id)


def test_explicit_branch_wins_over_the_creators_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    mine = make_branch(db, business, "Main", "MAIN", main=True)
    target = make_branch(db, business)
    put_user_in(db, test_data["manager"], mine)

    for response in create_each(
        client, auth_headers(test_data["manager"]), target.id
    ):
        assert response.status_code == 201, response.text
        assert response.json()["branch_id"] == str(target.id)


def test_new_records_refuse_inactive_or_foreign_branches(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    make_branch(db, business, "Main", "MAIN", main=True)
    closed = make_branch(db, business, "Closed", "CLS", active=False)
    foreign = make_branch(
        db, test_data["business_b"], "Foreign", "FOR", main=True
    )
    headers = auth_headers(test_data["manager"])

    for response in create_each(client, headers, closed.id):
        assert response.status_code == 409, response.text

    for response in create_each(client, headers, foreign.id):
        assert response.status_code == 422, response.text

    assert db.query(FuneralCase).count() == 0
    assert db.query(Member).count() == 0
    assert db.query(Resource).count() == 0


def test_case_creation_audit_records_its_branch(
    client, db, test_data, auth_headers,
):
    main = make_branch(db, test_data["business_a"], "Main", "MAIN", main=True)

    cases, *_ = create_each(client, auth_headers(test_data["manager"]))
    created = audit(db, uuid.UUID(cases.json()["id"]), "case.created")

    assert created[0].details["branch_id"] == str(main.id)


# ============================================================
# FILTERING BY BRANCH
# ============================================================

def test_lists_can_be_filtered_by_branch(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    other = make_branch(db, business)

    in_main = (
        make_case(db, business, main),
        make_member(db, business, main),
        make_resource(db, business, main),
    )
    in_other = (
        make_case(db, business, other),
        make_member(db, business, other),
        make_resource(db, business, other),
    )
    put_user_in(db, test_data["manager"], other)
    put_user_in(db, test_data["staff"], main)

    headers = auth_headers(test_data["main_admin"])

    def ids(path, branch):
        response = client.get(
            f"{path}?branch_id={branch.id}", headers=headers
        )
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()}

    assert ids("/cases", other) == {str(in_other[0].id)}
    assert ids("/cases", main) == {str(in_main[0].id)}
    assert ids("/members", other) == {str(in_other[1].id)}
    assert ids("/resources", main) == {str(in_main[2].id)}
    assert ids("/users", other) == {str(test_data["manager"].id)}
    assert str(test_data["staff"].id) in ids("/users", main)

    # No filter still returns everything.
    unfiltered = client.get("/cases", headers=headers).json()
    assert len(unfiltered) == 2


def test_filtering_by_another_businesses_branch_returns_nothing(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    make_case(
        db, business, make_branch(db, business, "Main", "MAIN", main=True)
    )
    foreign = make_branch(
        db, test_data["business_b"], "Foreign", "FOR", main=True
    )

    response = client.get(
        f"/cases?branch_id={foreign.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200
    assert response.json() == []


# ============================================================
# TRANSFERS
# ============================================================

def test_case_can_be_moved_with_audit_that_holds_no_personal_data(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    target = make_branch(db, business)
    case = make_case(db, business, main)

    response = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(target.id)},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["branch_id"] == str(target.id)

    entry = audit(db, case.id, "case.branch_changed")[0]

    assert entry.user_id == test_data["manager"].id
    assert entry.details["from_branch_id"] == str(main.id)
    assert entry.details["to_branch_id"] == str(target.id)
    assert entry.details["case_number"] == case.case_number
    assert "Private Name" not in str(entry.details)


def test_member_resource_and_user_can_be_moved(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    target = make_branch(db, business)
    member = make_member(db, business, main)
    resource = make_resource(db, business, main)
    staff = test_data["staff"]
    put_user_in(db, staff, main)

    headers = auth_headers(test_data["manager"])
    body = {"branch_id": str(target.id)}

    moves = [
        (f"/members/{member.id}/transfer", "member"),
        (f"/resources/{resource.id}/transfer", "resource"),
        (f"/users/{staff.id}/transfer", "user"),
    ]

    for path, entity in moves:
        response = client.post(path, json=body, headers=headers)

        assert response.status_code == 200, response.text
        assert response.json()["branch_id"] == str(target.id)

    for record, entity in (
        (member, "member"),
        (resource, "resource"),
        (staff, "user"),
    ):
        entry = audit(db, record.id, f"{entity}.branch_changed")[0]

        assert entry.details["from_branch_id"] == str(main.id)
        assert entry.details["to_branch_id"] == str(target.id)

    # The staff audit entry carries no email or name.
    user_entry = audit(db, staff.id, "user.branch_changed")[0]
    assert staff.email not in str(user_entry.details)
    assert "Test Staff" not in str(user_entry.details)


def test_record_without_a_branch_can_be_moved_into_one(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    target = make_branch(db, business, "Main", "MAIN", main=True)
    case = make_case(db, business, None)

    response = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(target.id)},
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 200, response.text

    entry = audit(db, case.id, "case.branch_changed")[0]
    assert entry.details["from_branch_id"] is None


def test_transfer_rules(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    closed = make_branch(db, business, "Closed", "CLS", active=False)
    foreign = make_branch(
        db, test_data["business_b"], "Foreign", "FOR", main=True
    )
    case = make_case(db, business, main)
    archived = make_case(db, business, main, archived=True)
    headers = auth_headers(test_data["manager"])

    same = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(main.id)},
        headers=headers,
    )
    inactive = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(closed.id)},
        headers=headers,
    )
    other_business = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(foreign.id)},
        headers=headers,
    )
    unknown = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(uuid.uuid4())},
        headers=headers,
    )
    frozen = client.post(
        f"/cases/{archived.id}/transfer",
        json={"branch_id": str(closed.id)},
        headers=headers,
    )
    junk = client.post(
        f"/cases/{case.id}/transfer",
        json={"branch_id": str(main.id), "status": "closed"},
        headers=headers,
    )

    assert same.status_code == 409
    assert "Already in" in same.json()["detail"]
    assert inactive.status_code == 409
    assert other_business.status_code == 422
    assert unknown.status_code == 422
    assert frozen.status_code == 409
    assert "Archived" in frozen.json()["detail"]
    assert junk.status_code == 422

    db.refresh(case)
    db.refresh(archived)
    assert case.branch_id == main.id
    assert archived.branch_id == main.id
    assert audit(db, case.id, "case.branch_changed") == []


def test_transfers_need_the_transfer_permission(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    target = make_branch(db, business)
    case = make_case(db, business, main)
    member = make_member(db, business, main)
    resource = make_resource(db, business, main)
    body = {"branch_id": str(target.id)}

    staff = auth_headers(test_data["staff"])

    for path in (
        f"/cases/{case.id}/transfer",
        f"/members/{member.id}/transfer",
        f"/resources/{resource.id}/transfer",
        f"/users/{test_data['staff'].id}/transfer",
    ):
        assert client.post(path, json=body, headers=staff).status_code == 403

    manager = test_data["manager"]
    set_permission(db, manager.id, "branches.transfer", "deny")

    assert client.post(
        f"/cases/{case.id}/transfer",
        json=body,
        headers=auth_headers(manager),
    ).status_code == 403

    db.refresh(case)
    assert case.branch_id == main.id


def test_moving_staff_follows_the_role_rules(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    target = make_branch(db, business)
    body = {"branch_id": str(target.id)}

    manager = test_data["manager"]
    admin = test_data["main_admin"]
    for user in (manager, admin, test_data["staff"]):
        put_user_in(db, user, main)

    as_manager = auth_headers(manager)

    # A manager cannot move another manager's peer, themselves or
    # the main admin.
    other_manager = User(
        business_id=business.id,
        branch_id=main.id,
        full_name="Second Manager",
        email=f"second-{uuid.uuid4().hex[:6]}@example.com",
        password_hash=manager.password_hash,
        role="manager",
        is_active=True,
    )
    db.add(other_manager)
    db.commit()

    for target_user in (manager, admin, other_manager):
        response = client.post(
            f"/users/{target_user.id}/transfer",
            json=body,
            headers=as_manager,
        )
        assert response.status_code == 403, response.text

    # The main admin can move a manager.
    moved = client.post(
        f"/users/{other_manager.id}/transfer",
        json=body,
        headers=auth_headers(admin),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["branch_id"] == str(target.id)

    # Nobody moves the main admin.
    assert client.post(
        f"/users/{admin.id}/transfer",
        json=body,
        headers=auth_headers(admin),
    ).status_code == 403


def test_other_business_cannot_move_records(
    client, db, test_data, auth_headers,
):
    business = test_data["business_a"]
    main = make_branch(db, business, "Main", "MAIN", main=True)
    foreign_branch = make_branch(
        db, test_data["business_b"], "Foreign", "FOR", main=True
    )
    case = make_case(db, business, main)
    member = make_member(db, business, main)
    resource = make_resource(db, business, main)
    outsider = auth_headers(test_data["other_business_manager"])

    for path in (
        f"/cases/{case.id}/transfer",
        f"/members/{member.id}/transfer",
        f"/resources/{resource.id}/transfer",
        f"/users/{test_data['staff'].id}/transfer",
    ):
        response = client.post(
            path,
            json={"branch_id": str(foreign_branch.id)},
            headers=outsider,
        )

        assert response.status_code == 404, response.text

    db.refresh(case)
    assert case.branch_id == main.id
