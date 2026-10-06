from app.models.group import Group, GroupMember


# ============================================================
# CREATE GROUP
# ============================================================

def test_user_can_create_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.post(
        "/groups",
        json={
            "name": "Operations Team",
            "description": "Funeral operations staff",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["name"] == "Operations Team"
    assert body["description"] == "Funeral operations staff"
    assert body["business_id"] == str(test_data["business_a"].id)
    assert body["created_by"] == str(staff.id)

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == body["id"],
        GroupMember.user_id == staff.id,
    ).first()

    assert membership is not None
    assert membership.is_admin is True


# ============================================================
# LIST GROUPS
# ============================================================

def test_user_can_list_groups(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        description="Operations",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.get(
        "/groups",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    groups = response.json()

    assert len(groups) == 1
    assert groups[0]["id"] == str(group.id)
    assert groups[0]["name"] == "Operations Team"


# ============================================================
# GET GROUP
# ============================================================

def test_user_can_get_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        description="Operations",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.get(
        f"/groups/{group.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == str(group.id)


# ============================================================
# UPDATE GROUP
# ============================================================

def test_group_admin_can_update_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Old Name",
        description="Old description",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "New Name",
            "description": "New description",
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "New Name"
    assert response.json()["description"] == "New description"


# ============================================================
# ADD GROUP MEMBER
# ============================================================

def test_group_admin_can_add_member(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        description=None,
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(manager.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["group_id"] == str(group.id)
    assert body["user_id"] == str(manager.id)
    assert body["is_admin"] is False


# ============================================================
# PROMOTE MEMBER
# ============================================================

def test_group_admin_can_promote_member(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=False,
        ),
    ])
    db.commit()

    response = client.patch(
        f"/groups/{group.id}/members/{manager.id}",
        json={
            "is_admin": True,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_admin"] is True


# ============================================================
# DEMOTE MEMBER
# ============================================================

def test_group_admin_can_demote_member(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=True,
        ),
    ])
    db.commit()

    response = client.patch(
        f"/groups/{group.id}/members/{manager.id}",
        json={
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_admin"] is False


# ============================================================
# REMOVE MEMBER
# ============================================================

def test_group_admin_can_remove_member(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=False,
        ),
    ])
    db.commit()

    response = client.delete(
        f"/groups/{group.id}/members/{manager.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 204

    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group.id,
        GroupMember.user_id == manager.id,
    ).first()

    assert membership is None


# ============================================================
# LAST ADMIN PROTECTION
# ============================================================

def test_cannot_demote_last_group_admin(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.patch(
        f"/groups/{group.id}/members/{staff.id}",
        json={
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "A group must always have at least one administrator"
    )


def test_cannot_remove_last_group_admin(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.delete(
        f"/groups/{group.id}/members/{staff.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "A group must always have at least one administrator"
    )


# ============================================================
# NON-ADMIN MEMBER CANNOT MANAGE GROUP
# ============================================================

def test_non_admin_group_member_cannot_manage_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=False,
        ),
    ])
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Changed By Non Admin",
        },
        headers=auth_headers(manager),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Group administrator access required"


# ============================================================
# CROSS-BUSINESS MEMBER PROTECTION
# ============================================================

def test_cannot_add_user_from_another_business(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_manager = test_data["other_business_manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(other_manager.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# ============================================================
# DUPLICATE MEMBER PROTECTION
# ============================================================

def test_cannot_add_duplicate_group_member(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=False,
        ),
    ])
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(manager.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "User is already a member of this group"


# ============================================================
# DELETE GROUP
# ============================================================

def test_group_admin_can_delete_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    group_id = group.id

    response = client.delete(
        f"/groups/{group_id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 204

    assert db.query(Group).filter(
        Group.id == group_id
    ).first() is None

    assert db.query(GroupMember).filter(
        GroupMember.group_id == group_id
    ).count() == 0


# ============================================================
# LIST GROUP MEMBERS
# ============================================================

def test_user_can_list_group_members(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        description="Operations",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add_all([
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        ),
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=False,
        ),
    ])
    db.commit()

    response = client.get(
        f"/groups/{group.id}/members",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200, response.text

    members = response.json()

    assert len(members) == 2
    assert members[0]["user_id"] == str(staff.id)
    assert members[0]["is_admin"] is True
    assert members[1]["user_id"] == str(manager.id)
    assert members[1]["is_admin"] is False


def test_cannot_list_group_members_from_another_business(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_manager = test_data["other_business_manager"]
    other_business = test_data["business_b"]

    group = Group(
        business_id=other_business.id,
        name="Other Business Group",
        description="Other business",
        created_by=other_manager.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=other_manager.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.get(
        f"/groups/{group.id}/members",
        headers=auth_headers(staff),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Group not found"


# ============================================================
# SECURITY / EDGE CASES
# ============================================================

def test_staff_cannot_delete_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=False,
        )
    )
    db.commit()

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Group administrator access required"


def test_staff_cannot_manage_group_members(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=manager.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(staff.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Group administrator access required"


def test_other_business_cannot_update_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_business_manager = test_data["other_business_manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Private Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Unauthorized Change",
        },
        headers=auth_headers(other_business_manager),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Group not found"


def test_other_business_cannot_delete_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_business_manager = test_data["other_business_manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Private Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(other_business_manager),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Group not found"


def test_inactive_user_cannot_be_added_to_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    manager.is_active = False
    db.flush()

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(manager.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Inactive users cannot be added to groups"
    )


def test_main_admin_can_manage_group_without_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Main Admin Managed Team",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Main Admin Managed Team"


# ============================================================
# SECURITY / EDGE CASES
# ============================================================

def test_staff_cannot_delete_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=False,
        )
    )
    db.commit()

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Group administrator access required"


def test_staff_cannot_manage_group_members(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=manager.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=manager.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(staff.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "Group administrator access required"


def test_other_business_cannot_update_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_business_manager = test_data["other_business_manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Private Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Unauthorized Change",
        },
        headers=auth_headers(other_business_manager),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Group not found"


def test_other_business_cannot_delete_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_business_manager = test_data["other_business_manager"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Private Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.delete(
        f"/groups/{group.id}",
        headers=auth_headers(other_business_manager),
    )

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Group not found"


def test_inactive_user_cannot_be_added_to_group(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]
    business = test_data["business_a"]

    manager.is_active = False
    db.flush()

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.flush()

    db.add(
        GroupMember(
            group_id=group.id,
            user_id=staff.id,
            is_admin=True,
        )
    )
    db.commit()

    response = client.post(
        f"/groups/{group.id}/members",
        json={
            "user_id": str(manager.id),
            "is_admin": False,
        },
        headers=auth_headers(staff),
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == (
        "Inactive users cannot be added to groups"
    )


def test_main_admin_can_manage_group_without_membership(
    client,
    db,
    test_data,
    auth_headers,
):
    main_admin = test_data["main_admin"]
    staff = test_data["staff"]
    business = test_data["business_a"]

    group = Group(
        business_id=business.id,
        name="Operations Team",
        created_by=staff.id,
    )
    db.add(group)
    db.commit()

    response = client.patch(
        f"/groups/{group.id}",
        json={
            "name": "Main Admin Managed Team",
        },
        headers=auth_headers(main_admin),
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Main Admin Managed Team"
