import uuid

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_permission
from app.models.business import Business
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user import User


def create_permission_test_data(db):
    business = Business(
        id=uuid.uuid4(),
        name=f"Permission Dependency Business {uuid.uuid4().hex[:8]}",
        slug=f"permission-dependency-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(business)
    db.flush()

    user = User(
        id=uuid.uuid4(),
        business_id=business.id,
        full_name="Permission Dependency User",
        email=f"permission-dependency-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-password-hash",
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.flush()

    permission = Permission(
        key="cases.view",
        description="View funeral cases",
        is_active=True,
    )
    db.add(permission)
    db.flush()

    return business, user, permission


def build_test_app(current_user, db):
    app = FastAPI()

    def override_current_user():
        return current_user

    def override_db():
        return db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db

    @app.get(
        "/protected",
        dependencies=[Depends(require_permission("cases.view"))],
    )
    def protected():
        return {"ok": True}

    return app


def test_permission_dependency_allows_role_permission(db):
    business, user, permission = create_permission_test_data(db)

    db.add(
        RolePermission(
            role="staff",
            permission_id=permission.id,
        )
    )
    db.commit()

    current_user = {
        "user_id": user.id,
        "auth_type": "business_user",
        "business_id": business.id,
        "role": "staff",
    }

    app = build_test_app(current_user, db)
    client = TestClient(app)

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_permission_dependency_denies_without_permission(db):
    business, user, permission = create_permission_test_data(db)

    db.commit()

    current_user = {
        "user_id": user.id,
        "auth_type": "business_user",
        "business_id": business.id,
        "role": "staff",
    }

    app = build_test_app(current_user, db)
    client = TestClient(app)

    response = client.get("/protected")

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.view"


def test_permission_dependency_respects_user_deny(db):
    business, user, permission = create_permission_test_data(db)

    db.add(
        RolePermission(
            role="staff",
            permission_id=permission.id,
        )
    )

    from app.models.user_permission import UserPermission

    db.add(
        UserPermission(
            user_id=user.id,
            permission_id=permission.id,
            effect="deny",
        )
    )

    db.commit()

    current_user = {
        "user_id": user.id,
        "auth_type": "business_user",
        "business_id": business.id,
        "role": "staff",
    }

    app = build_test_app(current_user, db)
    client = TestClient(app)

    response = client.get("/protected")

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission required: cases.view"


def test_permission_dependency_allows_main_admin(db):
    business, user, permission = create_permission_test_data(db)

    user.role = "main_admin"
    db.commit()

    current_user = {
        "user_id": user.id,
        "auth_type": "business_user",
        "business_id": business.id,
        "role": "main_admin",
    }

    app = build_test_app(current_user, db)
    client = TestClient(app)

    response = client.get("/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
