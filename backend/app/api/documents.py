from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.case_document import CaseDocument
from app.models.funeral_case import FuneralCase
from app.schemas.case_document import (
    CaseDocumentResponse,
    CaseDocumentUpdate,
)


router = APIRouter(
    prefix="/cases",
    tags=["Case Documents"],
)


# ============================================================
# STORAGE CONFIGURATION
# ============================================================

STORAGE_ROOT = Path("storage/documents")

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ============================================================
# AUTH HELPERS
# ============================================================

def get_user_business_id(current_user: dict) -> UUID:
    business_id = current_user.get("business_id")

    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User business information is missing",
        )

    try:
        return UUID(str(business_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid business ID",
        )


def get_user_id(current_user: dict) -> UUID:
    user_id = current_user.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User information is missing",
        )

    try:
        return UUID(str(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID",
        )


# ============================================================
# UPLOAD DOCUMENT
# POST /cases/{case_id}/documents
# ============================================================

@router.post(
    "/{case_id}/documents",
    response_model=CaseDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    case_id: UUID,
    document_type: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_permission("documents.manage")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)
    user_id = get_user_id(current_user)

    # --------------------------------------------------------
    # Verify funeral case
    # --------------------------------------------------------

    funeral_case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not funeral_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    safe_original_filename = Path(file.filename).name

    # --------------------------------------------------------
    # Validate MIME type
    # --------------------------------------------------------

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    file_content = file.file.read()

    # --------------------------------------------------------
    # Validate file size
    # --------------------------------------------------------

    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit",
        )

    # --------------------------------------------------------
    # Generate identifiers
    # --------------------------------------------------------

    document_id = uuid4()

    extension = Path(
        safe_original_filename
    ).suffix.lower()

    stored_filename = f"{document_id}{extension}"

    # --------------------------------------------------------
    # Create storage directory
    # --------------------------------------------------------

    document_directory = (
        STORAGE_ROOT
        / str(business_id)
        / str(case_id)
    )

    document_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = document_directory / stored_filename

    # --------------------------------------------------------
    # Save physical file
    # --------------------------------------------------------

    try:
        with open(file_path, "wb") as destination:
            destination.write(file_content)

    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document: {exc}",
        )

    # --------------------------------------------------------
    # Create database record
    # --------------------------------------------------------

    document = CaseDocument(
        id=document_id,
        business_id=business_id,
        case_id=case_id,
        document_type=document_type,
        original_filename=safe_original_filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        mime_type=file.content_type,
        file_size=len(file_content),
        description=description,
        uploaded_by=user_id,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()

        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save document record",
        )

    return document


# ============================================================
# LIST DOCUMENTS
# GET /cases/{case_id}/documents
# ============================================================

@router.get(
    "/{case_id}/documents",
    response_model=list[CaseDocumentResponse],
)
def list_documents(
    case_id: UUID,
    current_user: dict = Depends(require_permission("documents.view")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)

    funeral_case = (
        db.query(FuneralCase)
        .filter(
            FuneralCase.id == case_id,
            FuneralCase.business_id == business_id,
        )
        .first()
    )

    if not funeral_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral case not found",
        )

    return (
        db.query(CaseDocument)
        .filter(
            CaseDocument.case_id == case_id,
            CaseDocument.business_id == business_id,
        )
        .order_by(
            CaseDocument.created_at.desc()
        )
        .all()
    )


# ============================================================
# GET SINGLE DOCUMENT
# GET /cases/documents/{document_id}
# ============================================================

@router.get(
    "/documents/{document_id}",
    response_model=CaseDocumentResponse,
)
def get_document(
    document_id: UUID,
    current_user: dict = Depends(require_permission("documents.view")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)

    document = (
        db.query(CaseDocument)
        .filter(
            CaseDocument.id == document_id,
            CaseDocument.business_id == business_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


# ============================================================
# DOWNLOAD DOCUMENT
# GET /cases/documents/{document_id}/download
# ============================================================

@router.get(
    "/documents/{document_id}/download",
)
def download_document(
    document_id: UUID,
    current_user: dict = Depends(require_permission("documents.view")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)

    # --------------------------------------------------------
    # Find document
    # --------------------------------------------------------

    document = (
        db.query(CaseDocument)
        .filter(
            CaseDocument.id == document_id,
            CaseDocument.business_id == business_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # --------------------------------------------------------
    # Verify physical file exists
    # --------------------------------------------------------

    file_path = Path(document.file_path)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on storage",
        )

    # --------------------------------------------------------
    # Return file
    # --------------------------------------------------------

    return FileResponse(
        path=file_path,
        media_type=document.mime_type or "application/octet-stream",
        filename=document.original_filename,
    )


# ============================================================
# UPDATE DOCUMENT
# PATCH /cases/documents/{document_id}
# ============================================================

@router.patch(
    "/documents/{document_id}",
    response_model=CaseDocumentResponse,
)
def update_document(
    document_id: UUID,
    payload: CaseDocumentUpdate,
    current_user: dict = Depends(require_permission("documents.manage")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)

    document = (
        db.query(CaseDocument)
        .filter(
            CaseDocument.id == document_id,
            CaseDocument.business_id == business_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(document, field, value)

    db.commit()
    db.refresh(document)

    return document


# ============================================================
# DELETE DOCUMENT
# DELETE /cases/documents/{document_id}
# ============================================================

@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(
    document_id: UUID,
    current_user: dict = Depends(require_permission("documents.manage")),
    db: Session = Depends(get_db),
):
    business_id = get_user_business_id(current_user)

    document = (
        db.query(CaseDocument)
        .filter(
            CaseDocument.id == document_id,
            CaseDocument.business_id == business_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # --------------------------------------------------------
    # Delete physical file
    # --------------------------------------------------------

    file_path = Path(document.file_path)

    try:
        if file_path.exists():
            file_path.unlink()

    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document file: {exc}",
        )

    # --------------------------------------------------------
    # Delete database record
    # --------------------------------------------------------

    db.delete(document)
    db.commit()

    return None
