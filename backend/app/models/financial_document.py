import uuid

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


DOCUMENT_TYPES = ("quote", "invoice")

DOCUMENT_STATUSES = (
    "draft",
    "issued",
    "accepted",
    "declined",
    "converted",
    "void",
)


class FinancialDocument(Base):
    """
    A quote or an invoice for a funeral case.

    Drafts are editable and have no number. Issuing a document assigns
    its number and freezes it: an issued document is never edited or
    deleted, only voided with a reason. That keeps the financial
    history trustworthy.
    """

    __tablename__ = "financial_documents"

    __table_args__ = (
        CheckConstraint(
            "document_type IN ('quote', 'invoice')",
            name="ck_financial_documents_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'issued', 'accepted', 'declined', "
            "'converted', 'void')",
            name="ck_financial_documents_status",
        ),
        CheckConstraint(
            "subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0",
            name="ck_financial_documents_amounts",
        ),
        CheckConstraint(
            "discount <= subtotal",
            name="ck_financial_documents_discount",
        ),
        Index(
            "uq_financial_documents_business_number",
            "business_id",
            "number",
            unique=True,
            postgresql_where="number IS NOT NULL",
        ),
        # A case can only carry one live issued invoice at a time.
        Index(
            "uq_financial_documents_one_issued_invoice_per_case",
            "case_id",
            unique=True,
            postgresql_where=(
                "document_type = 'invoice' AND status = 'issued'"
            ),
        ),
        # A quote can only be converted into one non-void invoice.
        Index(
            "uq_financial_documents_one_invoice_per_quote",
            "source_quote_id",
            unique=True,
            postgresql_where=(
                "source_quote_id IS NOT NULL AND status <> 'void'"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Assigned when the document is issued.
    number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    tax: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Quotes only.
    valid_until: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Invoices only.
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_documents.id", ondelete="RESTRICT"),
        nullable=True,
    )

    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    voided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    void_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class FinancialDocumentLine(Base):
    __tablename__ = "financial_document_lines"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_financial_document_lines_quantity",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_financial_document_lines_unit_price",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1.00"),
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    case_service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_services.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PaymentReceipt(Base):
    """
    An immutable receipt for a recorded case payment.

    The receipt snapshots the payment at issue time. Once a payment has
    a receipt, the payment can no longer be edited or deleted.
    """

    __tablename__ = "payment_receipts"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            name="uq_payment_receipts_payment",
        ),
        UniqueConstraint(
            "business_id",
            "receipt_number",
            name="uq_payment_receipts_business_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("case_payments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    receipt_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    case_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    payment_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
