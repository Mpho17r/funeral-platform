"""membership on/off switch

Revision ID: d2b4c5d6e781
Revises: c1a3b4c5d670
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2b4c5d6e781'
down_revision: Union[str, Sequence[str], None] = 'c1a3b4c5d670'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('membership_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('businesses', 'membership_enabled')
