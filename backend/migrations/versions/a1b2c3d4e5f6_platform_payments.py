"""record LINDA platform subscription payments

Revision ID: a1b2c3d4e5f6
Revises: z6d8e9f0a12b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z6d8e9f0a12b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False, server_default="payfast"),
        sa.Column("merchant_payment_id", sa.String(100), nullable=False),
        sa.Column("provider_payment_id", sa.String(100), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("provider_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("merchant_payment_id", name="uq_platform_payment_merchant_id"),
        sa.UniqueConstraint("provider_payment_id", name="uq_platform_payment_provider_id"),
    )
    op.create_index("ix_platform_payments_business_id", "platform_payments", ["business_id"])


def downgrade() -> None:
    op.drop_index("ix_platform_payments_business_id", table_name="platform_payments")
    op.drop_table("platform_payments")
