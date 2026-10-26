"""add tax treatment and VAT snapshots to financial documents

Revision ID: b8c9d0e1f234
Revises: a7b8c9d0e123
Create Date: 2026-10-26 00:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f234"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("financial_documents", sa.Column("vat_registered_snapshot", sa.Boolean(), nullable=True))
    op.add_column("financial_documents", sa.Column("prices_include_vat_snapshot", sa.Boolean(), nullable=True))
    op.add_column("financial_documents", sa.Column("vat_rate_snapshot", sa.Numeric(5, 4), nullable=True))
    op.add_column("financial_document_lines", sa.Column("tax_treatment", sa.String(20), server_default="standard", nullable=False))
    op.add_column("financial_document_lines", sa.Column("vat_rate", sa.Numeric(5, 4), server_default="0.0000", nullable=False))
    op.add_column("financial_document_lines", sa.Column("taxable_value", sa.Numeric(12, 2), server_default="0.00", nullable=False))
    op.add_column("financial_document_lines", sa.Column("tax_amount", sa.Numeric(12, 2), server_default="0.00", nullable=False))
    op.alter_column("financial_document_lines", "tax_treatment", server_default=None)
    op.alter_column("financial_document_lines", "vat_rate", server_default=None)
    op.alter_column("financial_document_lines", "taxable_value", server_default=None)
    op.alter_column("financial_document_lines", "tax_amount", server_default=None)


def downgrade() -> None:
    op.drop_column("financial_document_lines", "tax_amount")
    op.drop_column("financial_document_lines", "taxable_value")
    op.drop_column("financial_document_lines", "vat_rate")
    op.drop_column("financial_document_lines", "tax_treatment")
    op.drop_column("financial_documents", "vat_rate_snapshot")
    op.drop_column("financial_documents", "prices_include_vat_snapshot")
    op.drop_column("financial_documents", "vat_registered_snapshot")
