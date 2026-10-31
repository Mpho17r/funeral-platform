"""business type: funeral or general

Revision ID: c1a3b4c5d670
Revises: b0f2a3b4c569
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1a3b4c5d670'
down_revision: Union[str, Sequence[str], None] = 'b0f2a3b4c569'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('business_type', sa.String(20), nullable=False, server_default='funeral'))
    # Standalone money received that is not a payment on a job.
    op.create_table(
        'income_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('branch_id', sa.Uuid(), sa.ForeignKey('branches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('income_date', sa.Date(), nullable=False, index=True),
        sa.Column('reference', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='recorded'),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('amount > 0', name='ck_income_entries_amount_positive'),
    )


def downgrade() -> None:
    op.drop_table('income_entries')
    op.drop_column('businesses', 'business_type')
