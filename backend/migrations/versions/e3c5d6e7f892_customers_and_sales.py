"""customers, sales documents, sale payments, supplier bills

Revision ID: e3c5d6e7f892
Revises: d2b4c5d6e781
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e3c5d6e7f892'
down_revision: Union[str, Sequence[str], None] = 'd2b4c5d6e781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id():
    return sa.Column('id', sa.Uuid(), primary_key=True)


def _biz():
    return sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)


def _by():
    return sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)


def _at():
    return sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        'customers', _id(), _biz(),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('phone', sa.String(50)),
        sa.Column('email', sa.String(255)),
        sa.Column('address', sa.Text()),
        sa.Column('tax_number', sa.String(50)),
        sa.Column('notes', sa.Text()),
        sa.Column('archived_at', sa.DateTime(timezone=True)),
        _by(), _at(),
    )
    op.create_table(
        'sales_documents', _id(), _biz(),
        sa.Column('customer_id', sa.Uuid(), sa.ForeignKey('customers.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('document_type', sa.String(10), nullable=False),
        sa.Column('status', sa.String(15), nullable=False, server_default='draft'),
        sa.Column('number', sa.String(30)),
        sa.Column('source_quote_id', sa.Uuid(), sa.ForeignKey('sales_documents.id', ondelete='SET NULL')),
        sa.Column('issue_date', sa.Date()),
        sa.Column('due_date', sa.Date(), index=True),
        sa.Column('valid_until', sa.Date()),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('discount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('tax', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text()),
        sa.Column('void_reason', sa.Text()),
        _by(), _at(),
        sa.UniqueConstraint('business_id', 'number', name='uq_sales_documents_number'),
        sa.CheckConstraint("document_type IN ('quote', 'invoice')", name='ck_sales_documents_type'),
    )
    op.create_table(
        'sales_lines', _id(),
        sa.Column('document_id', sa.Uuid(), sa.ForeignKey('sales_documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('line_total', sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        'sale_payments', _id(), _biz(),
        sa.Column('invoice_id', sa.Uuid(), sa.ForeignKey('sales_documents.id', ondelete='RESTRICT'), nullable=False, index=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('method', sa.String(30), nullable=False, server_default='cash'),
        sa.Column('reference', sa.String(255)),
        sa.Column('paid_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(15), nullable=False, server_default='recorded'),
        sa.Column('void_reason', sa.Text()),
        sa.Column('income_entry_id', sa.Uuid(), sa.ForeignKey('income_entries.id', ondelete='SET NULL')),
        _by(), _at(),
        sa.CheckConstraint('amount > 0', name='ck_sale_payments_amount_positive'),
    )
    op.create_table(
        'supplier_bills', _id(), _biz(),
        sa.Column('supplier_name', sa.String(200), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, server_default='other'),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('bill_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), index=True),
        sa.Column('reference', sa.String(255)),
        sa.Column('status', sa.String(10), nullable=False, server_default='unpaid'),
        sa.Column('paid_on', sa.Date()),
        sa.Column('expense_id', sa.Uuid(), sa.ForeignKey('expenses.id', ondelete='SET NULL')),
        sa.Column('void_reason', sa.Text()),
        _by(), _at(),
        sa.CheckConstraint('amount > 0', name='ck_supplier_bills_amount_positive'),
    )


def downgrade() -> None:
    op.drop_table('supplier_bills')
    op.drop_table('sale_payments')
    op.drop_table('sales_lines')
    op.drop_table('sales_documents')
    op.drop_table('customers')
