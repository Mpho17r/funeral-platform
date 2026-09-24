from datetime import date
from uuid import uuid4

from app.models.member import Member
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_permission import UserPermission


def grant_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            RolePermission(
                role=role,
                permission_id=permission.id,
            )
        )
        db.commit()


def revoke_permission(db, role, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(RolePermission)
        .filter(
            RolePermission.role == role,
            RolePermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is not None:
        db.delete(existing)
        db.commit()


def deny_permission(db, user_id, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )
    assert permission is not None

    existing = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

    if existing is None:
        db.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission.id,
                effect="deny",
            )
        )
    else:
        existing.effect = "deny"

    db.commit()


def create_member(db, business_id, prefix="MEM"):
    member = Member(
        business_id=business_id,
        member_number=f"{prefix}-{uuid4().hex[:8].upper()}",
        first_name="Test",
        last_name="Member",
        id_number="9001015009087",
        date_of_birth=date(1990, 1, 1),
        phone="0712345678",
        email="member@example.com",
        address="1 Test Street",
        join_date=date(2026, 1, 1),
        status="active",
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def member_payload(prefix="CREATE"):
    return {
        "member_number": f"{prefix}-{uuid4().hex[:8].upper()}",
        "first_name": "New",
        "last_name": "Member",
        "id_number": "9101015009088",
        "date_of_birth": "1991-01-01",
        "phone": "0723456789",
        "email": "newmember@example.com",
        "address": "2 Test Street",
        "join_date": "2026-01-01",
        "status": "active",
    }


# ---------------------------------------------------------------------------
# VIEW
# ---------------------------------------------------------------------------


def test_staff_with_members_view_can_list_members(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="VIEW",
    )

    grant_permission(
        db,
        "staff",
        "members.view",
    )

    response = client.get(
        "/members",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == str(member.id)
    assert data[0]["business_id"] == str(test_data["business_a"].id)


def test_staff_without_members_view_cannot_list_members(
    client,
    db,
    test_data,
    auth_headers,
):
    create_member(
        db,
        test_data["business_a"].id,
        prefix="NOVIEW",
    )

    revoke_permission(
        db,
        "staff",
        "members.view",
    )

    response = client.get(
        "/members",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: members.view"
    )


def test_staff_with_members_view_can_get_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="GET",
    )

    grant_permission(
        db,
        "staff",
        "members.view",
    )

    response = client.get(
        f"/members/{member.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(member.id)


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


def test_staff_with_members_create_can_create_member(
    client,
    db,
    test_data,
    auth_headers,
):
    grant_permission(
        db,
        "staff",
        "members.create",
    )

    response = client.post(
        "/members",
        json=member_payload(),
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["member_number"].startswith("CREATE-")
    assert data["first_name"] == "New"
    assert data["last_name"] == "Member"
    assert data["business_id"] == str(test_data["business_a"].id)


def test_staff_without_members_create_cannot_create_member(
    client,
    db,
    test_data,
    auth_headers,
):
    revoke_permission(
        db,
        "staff",
        "members.create",
    )

    response = client.post(
        "/members",
        json=member_payload("NOCREATE"),
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: members.create"
    )


# ---------------------------------------------------------------------------
# EDIT
# ---------------------------------------------------------------------------


def test_staff_with_members_edit_can_update_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="EDIT",
    )

    grant_permission(
        db,
        "staff",
        "members.edit",
    )

    response = client.patch(
        f"/members/{member.id}",
        json={
            "first_name": "Updated",
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


def test_staff_without_members_edit_cannot_update_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="NOEDIT",
    )

    revoke_permission(
        db,
        "staff",
        "members.edit",
    )

    response = client.patch(
        f"/members/{member.id}",
        json={
            "first_name": "Should Not Change",
        },
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: members.edit"
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_staff_with_members_delete_can_delete_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="DELETE",
    )

    grant_permission(
        db,
        "staff",
        "members.delete",
    )

    response = client.delete(
        f"/members/{member.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    remaining = (
        db.query(Member)
        .filter(Member.id == member.id)
        .first()
    )

    assert remaining is None


def test_staff_without_members_delete_cannot_delete_member(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_a"].id,
        prefix="NODELETE",
    )

    revoke_permission(
        db,
        "staff",
        "members.delete",
    )

    response = client.delete(
        f"/members/{member.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: members.delete"
    )


# ---------------------------------------------------------------------------
# USER-LEVEL DENY OVERRIDE
# ---------------------------------------------------------------------------


def test_explicit_user_deny_overrides_members_view_role_permission(
    client,
    db,
    test_data,
    auth_headers,
):
    create_member(
        db,
        test_data["business_a"].id,
        prefix="DENY",
    )

    grant_permission(
        db,
        "staff",
        "members.view",
    )

    deny_permission(
        db,
        test_data["staff"].id,
        "members.view",
    )

    response = client.get(
        "/members",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: members.view"
    )


# ---------------------------------------------------------------------------
# TENANT ISOLATION
# ---------------------------------------------------------------------------


def test_staff_cannot_access_member_from_another_business(
    client,
    db,
    test_data,
    auth_headers,
):
    member = create_member(
        db,
        test_data["business_b"].id,
        prefix="OTHER",
    )

    grant_permission(
        db,
        "staff",
        "members.view",
    )

    response = client.get(
        f"/members/{member.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"
