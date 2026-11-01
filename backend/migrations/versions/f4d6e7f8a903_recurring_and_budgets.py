"""recurring items and budgets

Revision ID: f4d6e7f8a903
Revises: e3c5d6e7f892
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f4d6e7f8a903'
down_revision: Union[str, Sequence[str], None] = 'e3c5d6e7f892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'recurring_items',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('frequency', sa.String(10), nullable=False),
        sa.Column('next_date', sa.Date(), nullable=False, index=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_recorded_on', sa.Date(), nullable=True),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('amount > 0', name='ck_recurring_items_amount_positive'),
        sa.CheckConstraint("kind IN ('income', 'expense')", name='ck_recurring_items_kind'),
        sa.CheckConstraint("frequency IN ('weekly', 'monthly', 'yearly')", name='ck_recurring_items_frequency'),
    )
    op.create_table(
        'budgets',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('business_id', 'category', name='uq_budgets_business_category'),
        sa.CheckConstraint('amount > 0', name='ck_budgets_amount_positive'),
    )


def downgrade() -> None:
    op.drop_table('budgets')
    op.drop_table('recurring_items')
