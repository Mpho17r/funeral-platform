"""create financial documents, lines and payment receipts

Revision ID: c3e4a5b6d703
Revises: b2d3f4a5c602
Create Date: 2026-10-08 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e4a5b6d703'
down_revision: Union[str, Sequence[str], None] = 'b2d3f4a5c602'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'financial_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(length=20), nullable=False),
        sa.Column('number', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('discount', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('tax', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('total', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('source_quote_id', sa.UUID(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('issued_by', sa.UUID(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('voided_by', sa.UUID(), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('quote', 'invoice')",
            name='ck_financial_documents_type',
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'issued', 'accepted', 'declined', "
            "'converted', 'void')",
            name='ck_financial_documents_status',
        ),
        sa.CheckConstraint(
            'subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0',
            name='ck_financial_documents_amounts',
        ),
        sa.CheckConstraint(
            'discount <= subtotal',
            name='ck_financial_documents_discount',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['source_quote_id'], ['financial_documents.id'],
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['issued_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['voided_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_financial_documents_business_id'),
        'financial_documents', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_financial_documents_case_id'),
        'financial_documents', ['case_id'], unique=False,
    )
    op.create_index(
        op.f('ix_financial_documents_document_type'),
        'financial_documents', ['document_type'], unique=False,
    )
    op.create_index(
        op.f('ix_financial_documents_status'),
        'financial_documents', ['status'], unique=False,
    )
    op.create_index(
        'uq_financial_documents_business_number',
        'financial_documents',
        ['business_id', 'number'],
        unique=True,
        postgresql_where=sa.text('number IS NOT NULL'),
    )
    op.create_index(
        'uq_financial_documents_one_issued_invoice_per_case',
        'financial_documents',
        ['case_id'],
        unique=True,
        postgresql_where=sa.text(
            "document_type = 'invoice' AND status = 'issued'"
        ),
    )
    op.create_index(
        'uq_financial_documents_one_invoice_per_quote',
        'financial_documents',
        ['source_quote_id'],
        unique=True,
        postgresql_where=sa.text(
            "source_quote_id IS NOT NULL AND status <> 'void'"
        ),
    )

    op.create_table(
        'financial_document_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2),
                  nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('line_total', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('case_service_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'quantity > 0',
            name='ck_financial_document_lines_quantity',
        ),
        sa.CheckConstraint(
            'unit_price >= 0',
            name='ck_financial_document_lines_unit_price',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['document_id'], ['financial_documents.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_service_id'], ['case_services.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_financial_document_lines_business_id'),
        'financial_document_lines', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_financial_document_lines_document_id'),
        'financial_document_lines', ['document_id'], unique=False,
    )

    op.create_table(
        'payment_receipts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('payment_id', sa.UUID(), nullable=False),
        sa.Column('receipt_number', sa.String(length=50), nullable=False),
        sa.Column('case_number', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('payment_reference', sa.String(length=255), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('issued_by', sa.UUID(), nullable=True),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['payment_id'], ['case_payments.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['issued_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id', name='uq_payment_receipts_payment'),
        sa.UniqueConstraint(
            'business_id', 'receipt_number',
            name='uq_payment_receipts_business_number',
        ),
    )
    op.create_index(
        op.f('ix_payment_receipts_business_id'),
        'payment_receipts', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_payment_receipts_case_id'),
        'payment_receipts', ['case_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_payment_receipts_case_id'), table_name='payment_receipts'
    )
    op.drop_index(
        op.f('ix_payment_receipts_business_id'),
        table_name='payment_receipts',
    )
    op.drop_table('payment_receipts')

    op.drop_index(
        op.f('ix_financial_document_lines_document_id'),
        table_name='financial_document_lines',
    )
    op.drop_index(
        op.f('ix_financial_document_lines_business_id'),
        table_name='financial_document_lines',
    )
    op.drop_table('financial_document_lines')

    op.drop_index(
        'uq_financial_documents_one_invoice_per_quote',
        table_name='financial_documents',
    )
    op.drop_index(
        'uq_financial_documents_one_issued_invoice_per_case',
        table_name='financial_documents',
    )
    op.drop_index(
        'uq_financial_documents_business_number',
        table_name='financial_documents',
    )
    op.drop_index(
        op.f('ix_financial_documents_status'),
        table_name='financial_documents',
    )
    op.drop_index(
        op.f('ix_financial_documents_document_type'),
        table_name='financial_documents',
    )
    op.drop_index(
        op.f('ix_financial_documents_case_id'),
        table_name='financial_documents',
    )
    op.drop_index(
        op.f('ix_financial_documents_business_id'),
        table_name='financial_documents',
    )
    op.drop_table('financial_documents')
