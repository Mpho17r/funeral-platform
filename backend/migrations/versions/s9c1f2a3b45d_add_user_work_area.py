"""add work area to users

Revision ID: s9c1f2a3b45d
Revises: r8b0e1f2a34c
Create Date: 2026-10-20 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 's9c1f2a3b45d'
down_revision: Union[str, Sequence[str], None] = 'r8b0e1f2a34c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('work_area', sa.String(20), nullable=False,
                  server_default='general'),
    )


def downgrade() -> None:
    op.drop_column('users', 'work_area')
