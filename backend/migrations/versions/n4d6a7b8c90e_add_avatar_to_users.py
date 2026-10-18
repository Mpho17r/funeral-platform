"""add profile photo timestamp to users

Revision ID: n4d6a7b8c90e
Revises: m3c5f6a7b89d
Create Date: 2026-10-18 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n4d6a7b8c90e'
down_revision: Union[str, Sequence[str], None] = 'm3c5f6a7b89d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('avatar_updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'avatar_updated_at')
