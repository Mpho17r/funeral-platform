import uuid

from pathlib import Path

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

def test_business_user_cannot_list_documents_from_other_business_case(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_b"], "DOC-012")
    create_document(
        db,
        test_data["business_b"],
        case,
        test_data["other_business_manager"],
    )
    db.commit()

    response = client.get(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_business_user_cannot_upload_document_to_other_business_case(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_b"], "DOC-013")
    db.commit()

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["manager"]),
        data={
            "document_type": "id_document",
            "description": "Cross-business upload",
        },
        files={
            "file": (
                "test.pdf",
                BytesIO(b"test document"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_business_user_cannot_download_document_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
    tmp_path,
):
    case = create_case(db, test_data["business_b"], "DOC-014")
    file_path = tmp_path / "foreign-document.pdf"
    file_path.write_bytes(b"foreign document")

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_b"].id,
        case_id=case.id,
        document_type="id_document",
        original_filename="foreign-document.pdf",
        stored_filename="foreign-document.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=len(b"foreign document"),
        description="Foreign document",
        uploaded_by=test_data["other_business_manager"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()

    response = client.get(
        f"/cases/documents/{document.id}/download",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_business_user_cannot_update_document_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_b"], "DOC-015")
    document = create_document(
        db,
        test_data["business_b"],
        case,
        test_data["other_business_manager"],
    )
    db.commit()

    response = client.patch(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["manager"]),
        json={
            "description": "Should not update",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_business_user_cannot_delete_document_from_other_business(
    client,
    db,
    test_data,
    auth_headers,
    tmp_path,
):
    case = create_case(db, test_data["business_b"], "DOC-016")
    file_path = tmp_path / "foreign-delete.pdf"
    file_path.write_bytes(b"foreign delete")

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_b"].id,
        case_id=case.id,
        document_type="id_document",
        original_filename="foreign-delete.pdf",
        stored_filename="foreign-delete.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=len(b"foreign delete"),
        description="Foreign delete document",
        uploaded_by=test_data["other_business_manager"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()

    response = client.delete(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["manager"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
    assert file_path.exists()
    
def test_upload_document_rejects_unsupported_mime_type(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-017")
    db.commit()

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
        },
        files={
            "file": (
                "malware.exe",
                BytesIO(b"not an executable"),
                "application/x-msdownload",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_document_rejects_file_over_10_mb(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-018")
    db.commit()

    oversized_content = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
        },
        files={
            "file": (
                "oversized.pdf",
                BytesIO(oversized_content),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "File exceeds the 10 MB limit"


def test_upload_document_sanitizes_filename(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-019")
    db.commit()

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
            "description": "Filename sanitization test",
        },
        files={
            "file": (
                "../../private/test-document.pdf",
                BytesIO(b"safe document"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["original_filename"] == "test-document.pdf"
    assert data["stored_filename"].endswith(".pdf")
    assert ".." not in data["original_filename"]
    assert "/" not in data["original_filename"]

def test_upload_document_persists_record_and_physical_file(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-020")
    db.commit()

    content = b"proof of death document"

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "proof_of_death",
            "description": "Persistence test",
        },
        files={
            "file": (
                "proof.pdf",
                BytesIO(content),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201

    data = response.json()

    document = (
        db.query(CaseDocument)
        .filter(CaseDocument.id == data["id"])
        .first()
    )

    assert document is not None
    assert document.case_id == case.id
    assert document.business_id == test_data["business_a"].id
    assert document.document_type == "proof_of_death"
    assert document.original_filename == "proof.pdf"
    assert document.mime_type == "application/pdf"
    assert document.file_size == len(content)

    file_path = Path(document.file_path)

    assert file_path.exists()
    assert file_path.read_bytes() == content

    file_path.unlink(missing_ok=True)


def test_download_document_returns_correct_metadata_and_content(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-021")
    db.commit()

    content = b"downloadable funeral document"
    storage_dir = Path("storage/documents") / str(test_data["business_a"].id) / str(case.id)
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_path = storage_dir / "download-test.pdf"
    file_path.write_bytes(content)

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_a"].id,
        case_id=case.id,
        document_type="supporting_document",
        original_filename="download-test.pdf",
        stored_filename="download-test.pdf",
        file_path=str(file_path),
        mime_type="application/pdf",
        file_size=len(content),
        description="Download test",
        uploaded_by=test_data["staff"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    response = client.get(
        f"/cases/documents/{document.id}/download",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith("application/pdf")
    assert "download-test.pdf" in response.headers["content-disposition"]

    file_path.unlink(missing_ok=True)


def test_download_document_returns_404_when_physical_file_is_missing(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-022")
    db.commit()

    missing_file_path = (
        Path("storage/documents")
        / str(test_data["business_a"].id)
        / str(case.id)
        / "missing-file.pdf"
    )

    document = CaseDocument(
        id=uuid.uuid4(),
        business_id=test_data["business_a"].id,
        case_id=case.id,
        document_type="supporting_document",
        original_filename="missing-file.pdf",
        stored_filename="missing-file.pdf",
        file_path=str(missing_file_path),
        mime_type="application/pdf",
        file_size=123,
        description="Missing file test",
        uploaded_by=test_data["staff"].id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    assert not missing_file_path.exists()

    response = client.get(
        f"/cases/documents/{document.id}/download",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Document file not found on storage"


def test_upload_document_rejects_missing_filename(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-023")
    db.commit()

    response = client.post(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
        },
        files={
            "file": (
                "",
                BytesIO(b"document content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_upload_document_rejects_nonexistent_case(
    client,
    db,
    test_data,
    auth_headers,
):
    missing_case_id = uuid.uuid4()

    response = client.post(
        f"/cases/{missing_case_id}/documents",
        headers=auth_headers(test_data["staff"]),
        data={
            "document_type": "id_document",
        },
        files={
            "file": (
                "missing-case.pdf",
                BytesIO(b"document content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Funeral case not found"


def test_update_document_preserves_unspecified_fields(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-024")
    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    original_document_type = document.document_type
    original_filename = document.original_filename
    original_description = document.description

    response = client.patch(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
        json={
            "description": "Updated description only",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["description"] == "Updated description only"
    assert data["document_type"] == original_document_type
    assert data["original_filename"] == original_filename

    db.refresh(document)

    assert document.description == "Updated description only"
    assert document.document_type == original_document_type
    assert document.original_filename == original_filename
    assert document.description != original_description


def test_delete_document_removes_database_record(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-025")

    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    document_id = document.id

    response = client.delete(
        f"/cases/documents/{document_id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204

    deleted_document = (
        db.query(CaseDocument)
        .filter(CaseDocument.id == document_id)
        .first()
    )

    assert deleted_document is None


def test_list_documents_returns_newest_first(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-026")

    older_document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )

    newer_document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )

    older_document.created_at = datetime(
        2026, 9, 20, 10, 0, tzinfo=timezone.utc
    )
    newer_document.created_at = datetime(
        2026, 9, 21, 10, 0, tzinfo=timezone.utc
    )

    db.commit()

    response = client.get(
        f"/cases/{case.id}/documents",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2
    assert data[0]["id"] == str(newer_document.id)
    assert data[1]["id"] == str(older_document.id)


def test_delete_document_removes_physical_file(
    client,
    db,
    test_data,
    auth_headers,
):
    case = create_case(db, test_data["business_a"], "DOC-027")
    document = create_document(
        db,
        test_data["business_a"],
        case,
        test_data["staff"],
    )
    db.commit()

    file_path = Path(document.file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"test document")

    assert file_path.exists()

    response = client.delete(
        f"/cases/documents/{document.id}",
        headers=auth_headers(test_data["staff"]),
    )

    assert response.status_code == 204
    assert not file_path.exists()
