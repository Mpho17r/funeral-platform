"""The business's document library: contracts, licences, receipts."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.appointments import DOCUMENT_CATEGORIES, BusinessDocument
from app.models.sales import Customer
from app.models.user import User
from app.services import chat_files
from app.services import library as svc
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/library", tags=["Documents"])


class PatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = None
    customer_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    expires_on: date | None = None


def _ids(current_user):
    return UUID(str(current_user["business_id"])), UUID(str(current_user["user_id"]))


def _get(db, business_id, doc_id) -> BusinessDocument:
    doc = (
        db.query(BusinessDocument)
        .filter(BusinessDocument.id == doc_id, BusinessDocument.business_id == business_id)
        .first()
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


def _check_category(category: str) -> str:
    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(422, "Choose a document type from the list.")
    return category


def _check_customer(db, business_id, customer_id):
    if customer_id and not (
        db.query(Customer.id)
        .filter(Customer.id == customer_id, Customer.business_id == business_id)
        .first()
    ):
        raise HTTPException(404, "Customer not found")


def _out(doc: BusinessDocument, customer_names: dict, user_names: dict) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "category": doc.category,
        "customer_id": str(doc.customer_id) if doc.customer_id else None,
        "customer_name": customer_names.get(doc.customer_id),
        "notes": doc.notes,
        "expires_on": doc.expires_on.isoformat() if doc.expires_on else None,
        "expiry": svc.expiry_state(doc.expires_on),
        "file_name": doc.file_name,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "is_image": doc.content_type in chat_files.IMAGE_TYPES,
        "uploaded_by_name": user_names.get(doc.uploaded_by),
        "archived": doc.archived_at is not None,
        "created_at": doc.created_at.isoformat(),
    }


def _lookups(db, rows):
    customers = {r.customer_id for r in rows if r.customer_id}
    users = {r.uploaded_by for r in rows if r.uploaded_by}
    return (
        {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(customers))}
        if customers
        else {},
        {u.id: u.full_name for u in db.query(User).filter(User.id.in_(users))}
        if users
        else {},
    )


@router.get("")
def list_documents(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = None,
    customer_id: UUID | None = None,
    expiring: bool = False,
    archived: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.view")),
):
    business_id, _ = _ids(current_user)
    query = db.query(BusinessDocument).filter(BusinessDocument.business_id == business_id)
    query = query.filter(
        BusinessDocument.archived_at.is_not(None)
        if archived
        else BusinessDocument.archived_at.is_(None)
    )
    if category:
        query = query.filter(BusinessDocument.category == category)
    if customer_id:
        query = query.filter(BusinessDocument.customer_id == customer_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                BusinessDocument.title.ilike(like),
                BusinessDocument.file_name.ilike(like),
                BusinessDocument.notes.ilike(like),
                BusinessDocument.customer_id.in_(
                    db.query(Customer.id).filter(
                        Customer.business_id == business_id, Customer.name.ilike(like)
                    )
                ),
            )
        )
    rows = query.order_by(BusinessDocument.created_at.desc()).limit(500).all()
    if expiring:
        rows = [r for r in rows if svc.expiry_state(r.expires_on)]
    customers, users = _lookups(db, rows)

    live = (
        db.query(BusinessDocument)
        .filter(
            BusinessDocument.business_id == business_id,
            BusinessDocument.archived_at.is_(None),
        )
        .all()
    )
    return {
        "items": [_out(r, customers, users) for r in rows],
        "categories": list(DOCUMENT_CATEGORIES),
        "counts": {
            "total": len(live),
            "expired": sum(1 for d in live if svc.expiry_state(d.expires_on) == "expired"),
            "soon": sum(1 for d in live if svc.expiry_state(d.expires_on) == "soon"),
        },
    }


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    category: str = Form(default="other"),
    customer_id: UUID | None = Form(default=None),
    notes: str | None = Form(default=None, max_length=2000),
    expires_on: date | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.manage")),
):
    business_id, user_id = _ids(current_user)
    _check_category(category)
    _check_customer(db, business_id, customer_id)

    contents = await file.read(chat_files.MAX_BYTES + 1)
    try:
        name, media_type = svc.check_file(file.filename or "file", contents)
    except svc.LibraryError as exc:
        raise HTTPException(422, str(exc)) from exc

    doc = BusinessDocument(
        id=uuid4(),
        business_id=business_id,
        title=(title or "").strip() or name.rsplit(".", 1)[0][:200] or name,
        category=category,
        customer_id=customer_id,
        notes=(notes or "").strip() or None,
        expires_on=expires_on,
        file_name=name,
        content_type=media_type,
        size_bytes=len(contents),
        storage_name=str(uuid4()),
        uploaded_by=user_id,
    )
    svc.save(business_id, doc.id, contents)
    db.add(doc)
    create_audit_log(
        db, business_id=business_id, user_id=user_id, action="document.uploaded",
        entity_type="business_document", entity_id=doc.id,
        details={"title": doc.title, "category": category}, notes="Document uploaded.",
    )
    db.commit()
    customers, users = _lookups(db, [doc])
    return _out(doc, customers, users)


@router.patch("/{doc_id}")
def update_document(
    doc_id: UUID,
    data: PatchIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.manage")),
):
    business_id, user_id = _ids(current_user)
    doc = _get(db, business_id, doc_id)
    sent = data.model_fields_set

    if "title" in sent and data.title:
        doc.title = data.title.strip()
    if "category" in sent and data.category:
        doc.category = _check_category(data.category)
    if "customer_id" in sent:
        _check_customer(db, business_id, data.customer_id)
        doc.customer_id = data.customer_id
    if "notes" in sent:
        doc.notes = (data.notes or "").strip() or None
    if "expires_on" in sent:
        doc.expires_on = data.expires_on

    create_audit_log(
        db, business_id=business_id, user_id=user_id, action="document.updated",
        entity_type="business_document", entity_id=doc.id,
        details={"fields": sorted(sent)}, notes="Document details changed.",
    )
    db.commit()
    customers, users = _lookups(db, [doc])
    return _out(doc, customers, users)


@router.post("/{doc_id}/archive")
def archive_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.manage")),
):
    business_id, user_id = _ids(current_user)
    doc = _get(db, business_id, doc_id)
    doc.archived_at = datetime.now(timezone.utc)
    create_audit_log(
        db, business_id=business_id, user_id=user_id, action="document.archived",
        entity_type="business_document", entity_id=doc.id, notes="Document archived.",
    )
    db.commit()
    customers, users = _lookups(db, [doc])
    return _out(doc, customers, users)


@router.post("/{doc_id}/restore")
def restore_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.manage")),
):
    business_id, user_id = _ids(current_user)
    doc = _get(db, business_id, doc_id)
    doc.archived_at = None
    create_audit_log(
        db, business_id=business_id, user_id=user_id, action="document.restored",
        entity_type="business_document", entity_id=doc.id, notes="Document restored.",
    )
    db.commit()
    customers, users = _lookups(db, [doc])
    return _out(doc, customers, users)


@router.get("/{doc_id}/file")
def download_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("library.view")),
):
    business_id, _ = _ids(current_user)
    doc = _get(db, business_id, doc_id)
    path = svc.locate(business_id, doc.id)
    if path is None:
        raise HTTPException(404, "The file is missing from storage.")

    inline = doc.content_type in chat_files.IMAGE_TYPES or doc.content_type == "application/pdf"
    return FileResponse(
        path,
        media_type=doc.content_type,
        filename=doc.file_name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300"},
    )
