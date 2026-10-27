"""member region

Revision ID: e1c3d4e5f670
Revises: d0b2c3d4e56f
Create Date: 2026-10-27 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1c3d4e5f670'
down_revision: Union[str, Sequence[str], None] = 'd0b2c3d4e56f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('members', sa.Column('region', sa.String(100), nullable=True))
    op.create_index('ix_members_region', 'members', ['region'])


def downgrade() -> None:
    op.drop_index('ix_members_region', table_name='members')
    op.drop_column('members', 'region')
