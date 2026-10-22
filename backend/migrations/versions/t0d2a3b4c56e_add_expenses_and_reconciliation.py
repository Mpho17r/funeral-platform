"""add expenses and reconciliation

Revision ID: t0d2a3b4c56e
Revises: s9c1f2a3b45d
Create Date: 2026-10-21 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 't0d2a3b4c56e'
down_revision: Union[str, Sequence[str], None] = 's9c1f2a3b45d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fk(table, col='id', ondelete=None):
    return sa.ForeignKey(f'{table}.{col}', ondelete=ondelete)


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        'expenses',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid, _fk('businesses', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('branch_id', uuid, _fk('branches', ondelete='SET NULL')),
        sa.Column('case_id', uuid, _fk('funeral_cases', ondelete='SET NULL')),
        sa.Column('supplier_id', uuid, _fk('suppliers', ondelete='SET NULL')),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('reference', sa.String(255)),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('void_reason', sa.Text()),
        sa.Column('voided_at', sa.DateTime(timezone=True)),
        sa.Column('voided_by', uuid, _fk('users', ondelete='SET NULL')),
        sa.Column('created_by', uuid, _fk('users', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_expenses_business_id', 'expenses', ['business_id'])
    op.create_index('ix_expenses_case_id', 'expenses', ['case_id'])
    op.create_index('ix_expenses_business_date', 'expenses',
                    ['business_id', 'expense_date'])

    op.create_table(
        'reconciliations',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid, _fk('businesses', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('recon_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('receipts_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('expenses_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('expected_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('counted_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('variance', sa.Numeric(12, 2), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('reconciled_by', uuid, _fk('users', ondelete='SET NULL')),
        sa.Column('reconciled_at', sa.DateTime(timezone=True),
                  nullable=False),
        sa.UniqueConstraint('business_id', 'recon_date', 'payment_method',
                            name='uq_reconciliations_day_method'),
    )
    op.create_index('ix_reconciliations_business_id', 'reconciliations',
                    ['business_id'])


def downgrade() -> None:
    op.drop_table('reconciliations')
    op.drop_table('expenses')
