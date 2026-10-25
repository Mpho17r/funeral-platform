"""platform administrators, subscriptions and usage limits

Revision ID: c9a1b2c3d45e
Revises: b8f0a1b2c34d
Create Date: 2026-10-25 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c9a1b2c3d45e'
down_revision: Union[str, Sequence[str], None] = 'b8f0a1b2c34d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'platform_admins',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('full_name', sa.String(150), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    t = 'businesses'
    op.add_column(t, sa.Column('subscription_tier', sa.String(20),
                               nullable=False, server_default='starter'))
    op.add_column(t, sa.Column('subscription_status', sa.String(20),
                               nullable=False, server_default='active'))
    op.add_column(t, sa.Column('trial_ends_at',
                               sa.DateTime(timezone=True), nullable=True))
    for c in ('max_branches', 'max_users', 'max_members',
              'max_active_cases'):
        op.add_column(t, sa.Column(c, sa.Integer(), nullable=True))


def downgrade() -> None:
    t = 'businesses'
    for c in ('max_active_cases', 'max_members', 'max_users', 'max_branches',
              'trial_ends_at', 'subscription_status', 'subscription_tier'):
        op.drop_column(t, c)
    op.drop_table('platform_admins')
