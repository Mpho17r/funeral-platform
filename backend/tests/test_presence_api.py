from app.models.staff_presence import StaffPresence


def grant_permission(db, role, permission_key):
    from app.models.permission import Permission
    from app.models.role_permission import RolePermission

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


def deny_permission(db, user_id, permission_key):
    from app.models.permission import Permission
    from app.models.user_permission import UserPermission

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


def test_main_admin_can_view_presence(
    client,
    test_data,
    auth_headers,
):
    admin = test_data["main_admin"]

    response = client.get(
        "/presence",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_staff_can_view_presence(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/presence",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_staff_can_get_own_presence(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.get(
        "/presence/me",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == str(staff.id)
    assert data["business_id"] == str(staff.business_id)
    assert data["user_name"] == staff.full_name
    assert data["role"] == staff.role
    assert data["status"] == "offline"

    presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.user_id == staff.id,
            StaffPresence.business_id == staff.business_id,
        )
        .first()
    )

    assert presence is not None


def test_staff_can_update_own_presence(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "online",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == str(staff.id)
    assert data["status"] == "online"
    assert data["last_seen_at"] is not None


def test_check_in_records_check_in_time(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "checked_in",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "checked_in"
    assert data["checked_in_at"] is not None
    assert data["checked_out_at"] is None


def test_offline_records_check_out_time(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    check_in = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "checked_in",
        },
    )

    assert check_in.status_code == 200

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "offline",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "offline"
    assert data["checked_out_at"] is not None


def test_invalid_presence_status_is_rejected(
    client,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "working",
        },
    )

    assert response.status_code == 422


def test_presence_is_tenant_scoped(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    other_business_manager = test_data["other_business_manager"]

    db.add_all(
        [
            StaffPresence(
                business_id=staff.business_id,
                user_id=staff.id,
                status="online",
            ),
            StaffPresence(
                business_id=other_business_manager.business_id,
                user_id=other_business_manager.id,
                status="online",
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/presence",
        headers=auth_headers(staff),
    )

    assert response.status_code == 200

    rows = response.json()

    user_ids = {row["user_id"] for row in rows}

    assert str(staff.id) in user_ids
    assert str(other_business_manager.id) not in user_ids


def test_explicit_user_deny_blocks_presence_view(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(
        db,
        staff.id,
        "presence.view",
    )

    response = client.get(
        "/presence",
        headers=auth_headers(staff),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: presence.view"
    )


def test_explicit_user_deny_blocks_presence_manage(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]

    deny_permission(
        db,
        staff.id,
        "presence.manage",
    )

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "online",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Permission required: presence.manage"
    )


def test_presence_me_only_updates_authenticated_user(
    client,
    db,
    test_data,
    auth_headers,
):
    staff = test_data["staff"]
    manager = test_data["manager"]

    response = client.patch(
        "/presence/me",
        headers=auth_headers(staff),
        json={
            "status": "online",
            "user_id": str(manager.id),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == str(staff.id)
    assert data["user_id"] != str(manager.id)

    manager_presence = (
        db.query(StaffPresence)
        .filter(
            StaffPresence.user_id == manager.id,
            StaffPresence.business_id == manager.business_id,
        )
        .first()
    )

    assert manager_presence is None
