"""private family and member portal links

Revision ID: b8f0a1b2c34d
Revises: a7e9f0a1b23c
Create Date: 2026-10-25 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b8f0a1b2c34d'
down_revision: Union[str, Sequence[str], None] = 'a7e9f0a1b23c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'portal_links',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('case_id', uuid,
                  sa.ForeignKey('funeral_cases.id', ondelete='CASCADE')),
        sa.Column('member_id', uuid,
                  sa.ForeignKey('members.id', ondelete='CASCADE')),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_by', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "(kind = 'family' AND case_id IS NOT NULL AND member_id IS NULL)"
            " OR (kind = 'member' AND member_id IS NOT NULL"
            " AND case_id IS NULL)",
            name='ck_portal_links_target'),
    )
    for col in ('business_id', 'case_id', 'member_id'):
        op.create_index(f'ix_portal_links_{col}', 'portal_links', [col])


def downgrade() -> None:
    op.drop_table('portal_links')
