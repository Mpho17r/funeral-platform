"""add automatic reminder settings to businesses

Revision ID: o5e7b8c9d01f
Revises: n4d6a7b8c90e
Create Date: 2026-10-18 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'o5e7b8c9d01f'
down_revision: Union[str, Sequence[str], None] = 'n4d6a7b8c90e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'businesses',
        sa.Column(
            'auto_reminders_enabled', sa.Boolean(),
            server_default='false', nullable=False,
        ),
    )
    op.add_column(
        'businesses',
        sa.Column(
            'auto_reminders_last_run_at', sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'businesses',
        sa.Column('auto_reminders_last_count', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('businesses', 'auto_reminders_last_count')
    op.drop_column('businesses', 'auto_reminders_last_run_at')
    op.drop_column('businesses', 'auto_reminders_enabled')
