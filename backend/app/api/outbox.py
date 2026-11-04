"""Messages to customers: write, send, and keep a history."""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_permission
from app.models.appointments import ContactMessage
from app.models.business import Business
from app.models.sales import Customer, SalesDocument
from app.services import contact_messages as svc
from app.services import sales as sales_calc
from app.services.audit_service import create_audit_log
from app.services.permission_service import has_permission

router = APIRouter(prefix="/outbox", tags=["Customer messages"])


class ComposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    body: str = Field(min_length=1, max_length=2000)
    subject: str | None = Field(default=None, max_length=200)
    customer_id: UUID | None = None
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient: str | None = Field(default=None, max_length=255)


class CancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


def _ids(current_user):
    return UUID(str(current_user["business_id"])), UUID(str(current_user["user_id"]))


def _customer(db, business_id, customer_id) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.business_id == business_id)
        .first()
    )
    if customer is None:
        raise HTTPException(404, "Customer not found")
    return customer


def _get(db, business_id, message_id) -> ContactMessage:
    message = (
        db.query(ContactMessage)
        .filter(ContactMessage.id == message_id, ContactMessage.business_id == business_id)
        .first()
    )
    if message is None:
        raise HTTPException(404, "Message not found")
    return message


def _names(db, rows):
    ids = {m.customer_id for m in rows if m.customer_id}
    if not ids:
        return {}
    return {
        c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(ids)).all()
    }


@router.get("")
def list_messages(
    status: str | None = None,
    channel: str | None = None,
    customer_id: UUID | None = None,
    appointment_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.view")),
):
    business_id, _ = _ids(current_user)
    query = db.query(ContactMessage).filter(ContactMessage.business_id == business_id)
    if status:
        query = query.filter(ContactMessage.status == status)
    if channel:
        query = query.filter(ContactMessage.channel == channel)
    if customer_id:
        query = query.filter(ContactMessage.customer_id == customer_id)
    if appointment_id:
        query = query.filter(ContactMessage.appointment_id == appointment_id)

    rows = query.order_by(ContactMessage.created_at.desc()).limit(limit).all()
    names = _names(db, rows)
    waiting = (
        db.query(ContactMessage)
        .filter(ContactMessage.business_id == business_id, ContactMessage.status == "queued")
        .count()
    )
    return {
        "items": [svc.as_dict(m, names.get(m.customer_id)) for m in rows],
        "waiting": waiting,
        "email_ready": svc.message_delivery.email_configured(),
    }


@router.get("/templates")
def templates(
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.view")),
):
    business_id, _ = _ids(current_user)
    name = _customer(db, business_id, customer_id).name if customer_id else None
    business = db.get(Business, business_id)
    return svc.templates_for(name, business.name)


@router.post("", status_code=201)
def compose(
    data: ComposeIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.manage")),
):
    """Write a message. Email is sent straight away when email is set up;
    WhatsApp and SMS come back with a one-tap link."""
    business_id, user_id = _ids(current_user)

    name = (data.recipient_name or "").strip() or None
    recipient = (data.recipient or "").strip()
    if data.customer_id:
        customer = _customer(db, business_id, data.customer_id)
        name = name or customer.name
        if not recipient:
            recipient = (customer.email if data.channel == "email" else customer.phone) or ""
        if not recipient:
            raise HTTPException(
                422,
                f"{customer.name} has no "
                f"{'email address' if data.channel == 'email' else 'phone number'} saved.",
            )
    if not recipient:
        raise HTTPException(422, "Who is it going to? Choose a customer or type a number or email.")

    try:
        message = svc.queue(
            db,
            business_id=business_id,
            channel=data.channel,
            recipient=recipient,
            body=data.body,
            subject=data.subject,
            customer_id=data.customer_id,
            recipient_name=name,
            created_by=user_id,
        )
    except svc.MessageError as exc:
        raise HTTPException(422, str(exc)) from exc

    svc.try_send_now(message)
    create_audit_log(
        db, business_id=business_id, user_id=user_id, action="message.queued",
        entity_type="contact_message", entity_id=message.id,
        details={"channel": message.channel}, notes="Customer message written.",
    )
    db.commit()
    return svc.as_dict(message, name if data.customer_id else None)


@router.post("/invoice/{invoice_id}/reminder", status_code=201)
def invoice_reminder(
    invoice_id: UUID,
    channel: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.manage")),
):
    """A payment reminder for an unpaid invoice, with the amount and date."""
    business_id, user_id = _ids(current_user)
    if not has_permission(
        db, user_id=user_id, role=current_user["role"], permission_key="sales.view"
    ):
        raise HTTPException(403, "Permission required: sales.view")

    doc = (
        db.query(SalesDocument)
        .filter(
            SalesDocument.id == invoice_id,
            SalesDocument.business_id == business_id,
            SalesDocument.document_type == "invoice",
        )
        .first()
    )
    if doc is None:
        raise HTTPException(404, "Invoice not found")
    state = sales_calc.payment_state(doc, sales_calc.paid_amount(db, doc.id), date.today())
    if state["state"] in (None, "paid") or state["balance"] <= 0:
        raise HTTPException(409, "That invoice has nothing outstanding.")

    customer = _customer(db, business_id, doc.customer_id)
    business = db.get(Business, business_id)
    picked = svc.best_channel(customer.phone, customer.email, channel)
    if picked is None:
        raise HTTPException(422, f"{customer.name} has no usable phone number or email.")

    due = f" It was due on {doc.due_date:%d %B %Y}." if doc.due_date else ""
    body = (
        f"Hello {customer.name},\n\nA friendly reminder that invoice {doc.number} "
        f"from {business.name} has R{state['balance']:,.2f} outstanding.{due}"
        f"\n\nIf you have already paid, please ignore this message."
        f"\n\nKind regards,\n{business.name}"
    )
    try:
        message = svc.queue(
            db, business_id=business_id, channel=picked,
            recipient=customer.email if picked == "email" else customer.phone,
            body=body, subject=f"Reminder: invoice {doc.number}",
            customer_id=customer.id, recipient_name=customer.name,
            created_by=user_id,
        )
    except svc.MessageError as exc:
        raise HTTPException(422, str(exc)) from exc
    svc.try_send_now(message)
    db.commit()
    return svc.as_dict(message, customer.name)


@router.post("/{message_id}/send-email")
def send_email_now(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.manage")),
):
    business_id, _ = _ids(current_user)
    message = _get(db, business_id, message_id)
    try:
        svc.deliver_one(message)
    except svc.MessageError as exc:
        db.commit()  # keep the attempt and the reason on the message
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return svc.as_dict(message)


@router.post("/{message_id}/mark-sent")
def mark_sent(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.manage")),
):
    """A person sent a WhatsApp or SMS by hand and says so."""
    business_id, user_id = _ids(current_user)
    message = _get(db, business_id, message_id)
    if message.status != "queued":
        raise HTTPException(409, f"A {message.status} message cannot be marked sent.")
    message.status = "sent"
    message.sent_at = datetime.now(timezone.utc)
    message.sent_by = user_id
    message.delivered_by = "manual"
    db.commit()
    return svc.as_dict(message)


@router.post("/{message_id}/cancel")
def cancel_message(
    message_id: UUID,
    data: CancelIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("outbox.manage")),
):
    business_id, _ = _ids(current_user)
    message = _get(db, business_id, message_id)
    if message.status != "queued":
        raise HTTPException(409, f"A {message.status} message cannot be cancelled.")
    message.status = "cancelled"
    message.cancelled_at = datetime.now(timezone.utc)
    message.cancel_reason = data.reason.strip()
    db.commit()
    return svc.as_dict(message)
