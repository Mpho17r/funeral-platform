from datetime import datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CaseService(Base):
    __tablename__ = "case_services"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    business_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funeral_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    service_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    unit_price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    total_price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    scheduled_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
    )

    provider: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Optional link to a stocked item (a coffin, flowers...). When set,
    # stock is issued to the case automatically and put back if the line
    # is cancelled or deleted. stock_issued is how much is out right now.
    inventory_item_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_items.id"),
        nullable=True,
    )
    stock_issued: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    # Services work like tasks: someone is responsible, and they update
    # the status. A finished service is archived after a while.
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    archived_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    assignee_rows: Mapped[list["CaseServiceAssignee"]] = relationship(
        "CaseServiceAssignee",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CaseServiceAssignee.created_at",
    )

    @property
    def assignee_ids(self) -> list[UUID]:
        return [row.user_id for row in self.assignee_rows]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )



class CaseServiceAssignee(Base):
    __tablename__ = "case_service_assignees"
    __table_args__ = (
        UniqueConstraint("service_id", "user_id", name="uq_case_service_assignees"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_services.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
