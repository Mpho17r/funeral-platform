"""kai conversation memory and proposed actions

Revision ID: b4f6a7c8d903
Revises: a3e5f6b7c892
Create Date: 2026-10-27 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b4f6a7c8d903'
down_revision: Union[str, Sequence[str], None] = 'a3e5f6b7c892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.create_table(
        'kai_turns',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('speaker', sa.String(10), nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('items', JSONB, nullable=False, server_default='[]'),
        sa.Column('focus', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_kai_turns_business_id', 'kai_turns', ['business_id'])
    op.create_index('ix_kai_turns_user_id', 'kai_turns', ['user_id'])
    op.create_index('ix_kai_turns_created_at', 'kai_turns', ['created_at'])

    op.create_table(
        'kai_actions',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('params', JSONB, nullable=False, server_default='{}'),
        sa.Column('summary', sa.String(500), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_kai_actions_business_id', 'kai_actions', ['business_id'])
    op.create_index('ix_kai_actions_user_id', 'kai_actions', ['user_id'])


def downgrade() -> None:
    op.drop_table('kai_actions')
    op.drop_table('kai_turns')
