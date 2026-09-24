import uuid

from datetime import date, datetime, timezone
from io import BytesIO

from app.models.case_document import CaseDocument
from app.models.funeral_case import FuneralCase
from app.models.permission import Permission
from app.models.user_permission import UserPermission


def create_case(db, business, case_number):
    case = FuneralCase(
        id=uuid.uuid4(),
        business_id=business.id,
        case_number=case_number,
        deceased_full_name="Test Deceased",
        date_of_death=date(2026, 9, 20),
        funeral_date=date(2026, 9, 25),
        status="open",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    return case


def create_document(db, business, case, uploaded_by):
    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=business.id,
        case_id=case.id,
        document_type="id_document",
        original_filename="test-document.pdf",
        stored_filename="test-document.pdf",
        file_path="storage/documents/test-document.pdf",
        mime_type="application/pdf",
        file_size=1024,
        description="Test document",
        uploaded_by=uploaded_by.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.flush()
    return document


def deny_permission(db, user, permission_key):
    permission = (
        db.query(Permission)
        .filter(Permission.key == permission_key)
        .first()
    )

    assert permission is not None

    override = UserPermission(
        user_id=user.id,
        permission_id=permission.id,
        effect="deny",
    )

    db.add(override)
    db.commit()


# ============================================================
# VIEW PERMISSION
# ============================================================

def test_staff_with_document_view_permission_can_list_documents(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-001")
    create_document(db, test_data["business_a"], case, test_data["staff"])
    db.commit()

    response = client.get(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_staff_denied_document_view_cannot_list_documents(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-002")
    create_document(db, test_data["business_a"], case, test_data["staff"])
    db.commit()

    deny_permission(db, test_data["staff"], "documents.view")

    response = client.get(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403


def test_staff_with_document_view_permission_can_get_document(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-003")
    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    response = client.get(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)


# ============================================================
# MANAGE PERMISSION
# ============================================================

def test_staff_with_document_manage_permission_can_update_document(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-004")
    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    response = client.patch(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "document_type": "death_certificate",
            "description": "Updated document",
        },
    )

    assert response.status_code == 200
    assert response.json()["document_type"] == "death_certificate"
    assert response.json()["description"] == "Updated document"


def test_staff_denied_document_manage_cannot_update_document(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-005")
    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    deny_permission(db, test_data["staff"], "documents.manage")

    response = client.patch(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "description": "Should not update",
        },
    )

    assert response.status_code == 403


def test_staff_with_document_manage_permission_can_delete_document(
    client,
    db,
    test_data,
    auth_headers,
    tmp_path,
):
    case = create_case(db, test_data["business_a"], "DOC-006")

    file_path = tmp_path / "test-document.pdf"
    file_path.write_bytes(b"test document")

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_a"].id,
        case_id=case.id,
        document_type="id_document",
        original_filename="test-document.pdf",
        stored_filename="test-document.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=14,
        description="Test document",
        uploaded_by=test_data["staff"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(document)
    db.commit()

    response = client.delete(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204
    assert not file_path.exists()


def test_staff_denied_document_manage_cannot_delete_document(
    client,
    db,
    test_data,
    auth_headers,
    tmp_path,
):
    case = create_case(db, test_data["business_a"], "DOC-007")

    file_path = tmp_path / "protected-document.pdf"
    file_path.write_bytes(b"protected document")

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_a"].id,
        case_id=case.id,
        document_type="id_document",
        original_filename="protected-document.pdf",
        stored_filename="protected-document.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=18,
        description="Protected document",
        uploaded_by=test_data["staff"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(document)
    db.commit()

    deny_permission(db, test_data["staff"], "documents.manage")

    response = client.delete(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
    assert file_path.exists()


# ============================================================
# TENANT ISOLATION
# ============================================================

def test_business_user_cannot_access_document_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_b"], "DOC-008")

    document = create_document(
        db,
        test_data["business_b"],
        case,
        test_data["other_business_manager"],
    )
    db.commit()

    response = client.get(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404


# ============================================================
# UPLOAD PERMISSION
# ============================================================

def test_staff_denied_document_manage_cannot_upload_document(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-009")
    db.commit()

    deny_permission(db, test_data["staff"], "documents.manage")

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
            "description": "Should not upload",
        },
        files={
            "file": (
                "test.pdf",
                BytesIO(b"test document"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403


def test_staff_with_document_manage_permission_can_upload_document(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-010")
    db.commit()

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
            "description": "Uploaded test document",
        },
        files={
            "file": (
                "test.pdf",
                BytesIO(b"test document"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == "id_document"


# ============================================================
# DOWNLOAD PERMISSION
# ============================================================

def test_staff_denied_document_view_cannot_download_document(
    client,
    db,
    test_data,
    auth_headers,
    tmp_path,
):
    case = create_case(db, test_data["business_a"], "DOC-011")

    file_path = tmp_path / "download-test.pdf"
    file_path.write_bytes(b"download test")

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_a"].id,
        case_id=case.id,
        document_type="id_document",
        original_filename="download-test.pdf",
        stored_filename="download-test.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=13,
        description="Download test",
        uploaded_by=test_data["staff"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(document)
    db.commit()

    deny_permission(db, test_data["staff"], "documents.view")

    response = client.get(
        f"/cases/documents/{document.id}/download",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 403
