"""KAI Autopilot: platform-manager settings, items, task origin

Revision ID: a9e1f2a3b458
Revises: f8d0e1f2a347
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a9e1f2a3b458'
down_revision: Union[str, Sequence[str], None] = 'f8d0e1f2a347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('autopilot_mode', sa.String(10), nullable=False, server_default='off'))
    op.add_column('businesses', sa.Column('autopilot_create_tasks', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('businesses', sa.Column('autopilot_assign', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('businesses', sa.Column('autopilot_escalate', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('businesses', sa.Column('autopilot_max_open', sa.Integer(), nullable=False, server_default='8'))
    op.add_column('case_tasks', sa.Column('by_kai', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('case_tasks', sa.Column('auto_key', sa.String(120), nullable=True))
    op.create_index('ix_case_tasks_auto_key', 'case_tasks', ['auto_key'])
    op.create_table(
        'kai_autopilot_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('funeral_cases.id', ondelete='CASCADE'), nullable=True),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('dedupe_key', sa.String(200), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('params', postgresql.JSONB(), nullable=False),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_kai_autopilot_items_business_id', 'kai_autopilot_items', ['business_id'])
    op.create_index('ix_kai_autopilot_items_case_id', 'kai_autopilot_items', ['case_id'])
    op.create_index('ix_kai_autopilot_items_status', 'kai_autopilot_items', ['status'])
    op.create_index('ix_kai_autopilot_items_dedupe_key', 'kai_autopilot_items', ['dedupe_key'])


def downgrade() -> None:
    op.drop_table('kai_autopilot_items')
    op.drop_index('ix_case_tasks_auto_key', table_name='case_tasks')
    op.drop_column('case_tasks', 'auto_key')
    op.drop_column('case_tasks', 'by_kai')
    for c in ('autopilot_max_open', 'autopilot_escalate', 'autopilot_assign', 'autopilot_create_tasks', 'autopilot_mode'):
        op.drop_column('businesses', c)
