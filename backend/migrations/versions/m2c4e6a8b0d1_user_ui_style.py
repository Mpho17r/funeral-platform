"""user look preference (standard or glass)

Revision ID: m2c4e6a8b0d1
Revises: v0a7b9c2d3e4
Create Date: 2026-11-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'm2c4e6a8b0d1'
down_revision: Union[str, Sequence[str], None] = 'v0a7b9c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = never chosen, so the app asks once on first sign-in.
    op.add_column(
        'users',
        sa.Column('ui_style', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'ui_style')
