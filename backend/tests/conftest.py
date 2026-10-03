import os

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.business import Business
from app.models.user import User
from app.security import hash_password
from app.services.permission_seed import sync_permission_system


TEST_DATABASE_URL = "postgresql+psycopg://mac@localhost:5432/funeralos_test"


# ---------------------------------------------------------------------------
# SAFETY GUARDS
# ---------------------------------------------------------------------------
# Tests must NEVER connect to the development database.

if "funeralos_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        "Tests must use the funeralos_test database"
    )

if TEST_DATABASE_URL.endswith("/funeralos"):
    raise RuntimeError(
        "Refusing to run tests against development database"
    )


# ---------------------------------------------------------------------------
# TEST DATABASE ENGINE
# ---------------------------------------------------------------------------

engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# DATABASE FIXTURE
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """
    Provides a clean database session for every test.

    The database schema is managed by Alembic.
    This fixture only removes test data between tests.

    CASCADE is used because the application contains
    foreign-key relationships between tables.
    """

    session = TestingSessionLocal()

    try:
        # -------------------------------------------------------------------
        # TEST DATABASE CLEANUP
        # -------------------------------------------------------------------
        #
        # Keep every test isolated while preserving the
        # Alembic-managed schema.
        #
        # Important:
        # The permission tables contain seeded/default permissions
        # from the permission-system migration. They must also be
        # cleared before every test, otherwise tests that create
        # permissions such as "cases.view" will hit unique constraints.
        #
        # Membership tables are also included so membership tests
        # cannot leak data between tests.
        #
        # CASCADE handles foreign-key relationships.
        #

        tables = [
            # Permission system
            "user_permissions",
            "role_permissions",
            "permissions",

            # Membership system
            "membership_payments",
            "membership_contributions",
            "memberships",
            "covered_dependents",
            "membership_plan_benefits",
            "members",
            "membership_plans",

            # Funeral case system
            "case_payments",
            "case_financials",
            "case_services",
            "case_tasks",
            "case_documents",
            "case_contacts",
            "funeral_cases",

            # Audit
            "audit_logs",

            # User groups
            "group_members",
            "groups",

            # Core application tables
            "users",
            "businesses",
        ]

        for table in tables:
            session.execute(
                text(
                    f"TRUNCATE TABLE {table} "
                    "RESTART IDENTITY CASCADE"
                )
            )

        session.commit()

        # Rebuild the application permission catalogue and
        # default Manager/Staff role permissions for each test.

        yield session

    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# FASTAPI TEST CLIENT
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db):
    """
    FastAPI TestClient using the test database session.
    """

    # Seed the real application permission catalogue for API tests.
    sync_permission_system(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client

    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TEST DATA
# ---------------------------------------------------------------------------

@pytest.fixture
def test_data(db):
    """
    Creates two businesses and users belonging to those businesses.

    Business A:
        - Main Admin
        - Manager
        - Staff

    Business B:
        - Manager

    This allows tests to verify:
        - roles
        - authentication
        - tenant isolation
        - business ownership
    """

    # -----------------------------------------------------------------------
    # BUSINESSES
    # -----------------------------------------------------------------------

    business_a = Business(
        id=uuid4(),
        name="Test Funeral Business A",
        slug=f"test-business-a-{uuid4().hex[:8]}",
        is_active=True,
    )

    business_b = Business(
        id=uuid4(),
        name="Test Funeral Business B",
        slug=f"test-business-b-{uuid4().hex[:8]}",
        is_active=True,
    )

    db.add_all([
        business_a,
        business_b,
    ])

    db.flush()

    # -----------------------------------------------------------------------
    # PASSWORD
    # -----------------------------------------------------------------------

    password = "TestPassword123!"

    password_hash = hash_password(password)

    # -----------------------------------------------------------------------
    # USERS
    # -----------------------------------------------------------------------

    main_admin = User(
        business_id=business_a.id,
        full_name="Test Main Admin",
        email=f"main-admin-{uuid4().hex[:8]}@example.com",
        password_hash=password_hash,
        role="main_admin",
        is_active=True,
    )

    manager = User(
        business_id=business_a.id,
        full_name="Test Manager",
        email=f"manager-{uuid4().hex[:8]}@example.com",
        password_hash=password_hash,
        role="manager",
        is_active=True,
    )

    staff = User(
        business_id=business_a.id,
        full_name="Test Staff",
        email=f"staff-{uuid4().hex[:8]}@example.com",
        password_hash=password_hash,
        role="staff",
        is_active=True,
    )

    other_business_manager = User(
        business_id=business_b.id,
        full_name="Other Business Manager",
        email=f"other-manager-{uuid4().hex[:8]}@example.com",
        password_hash=password_hash,
        role="manager",
        is_active=True,
    )

    db.add_all([
        main_admin,
        manager,
        staff,
        other_business_manager,
    ])

    db.commit()

    return {
        "password": password,
        "business_a": business_a,
        "business_b": business_b,
        "main_admin": main_admin,
        "manager": manager,
        "staff": staff,
        "other_business_manager": other_business_manager,
    }


# ---------------------------------------------------------------------------
# AUTHENTICATION HEADERS
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_headers(client):
    """
    Returns a helper function that logs a test user in
    and returns the Authorization header.
    """

    def login(user):
        response = client.post(
            "/auth/login",
            json={
                "email": user.email,
                "password": "TestPassword123!",
            },
        )

        assert response.status_code == 200, response.text

        token = response.json()["access_token"]

        return {
            "Authorization": f"Bearer {token}",
        }

    return login
