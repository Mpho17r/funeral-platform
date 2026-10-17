"""add job title to users

Revision ID: m3c5f6a7b89d
Revises: l2b4e5f6a78c
Create Date: 2026-10-17 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm3c5f6a7b89d'
down_revision: Union[str, Sequence[str], None] = 'l2b4e5f6a78c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('job_title', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'job_title')
