"""add member archive and anonymise columns

Revision ID: l2b4e5f6a78c
Revises: k1a3d4e5f67b
Create Date: 2026-10-15 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'l2b4e5f6a78c'
down_revision: Union[str, Sequence[str], None] = 'k1a3d4e5f67b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('members', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('members', sa.Column('archived_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('members', sa.Column('archive_reason', sa.Text(), nullable=True))
    op.add_column('members', sa.Column('anonymised_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_members_archived_at'), 'members', ['archived_at'], unique=False)
    op.create_foreign_key(
        'fk_members_archived_by_users',
        'members',
        'users',
        ['archived_by'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_members_archived_by_users', 'members', type_='foreignkey')
    op.drop_index(op.f('ix_members_archived_at'), table_name='members')
    op.drop_column('members', 'anonymised_at')
    op.drop_column('members', 'archive_reason')
    op.drop_column('members', 'archived_by')
    op.drop_column('members', 'archived_at')
