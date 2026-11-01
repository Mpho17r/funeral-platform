"""leave requests and yearly allowance

Revision ID: g5e7f8a9b014
Revises: f4d6e7f8a903
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'g5e7f8a9b014'
down_revision: Union[str, Sequence[str], None] = 'f4d6e7f8a903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('leave_days_per_year', sa.Integer(), nullable=False, server_default='15'))
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('business_id', sa.Uuid(), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('leave_type', sa.String(20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False, index=True),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('days', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(15), nullable=False, server_default='pending', index=True),
        sa.Column('decided_by', sa.Uuid(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('end_date >= start_date', name='ck_leave_requests_dates'),
        sa.CheckConstraint('days > 0', name='ck_leave_requests_days_positive'),
    )


def downgrade() -> None:
    op.drop_table('leave_requests')
    op.drop_column('businesses', 'leave_days_per_year')
