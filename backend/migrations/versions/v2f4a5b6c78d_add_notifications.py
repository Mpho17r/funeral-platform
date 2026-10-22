"""add notifications

Revision ID: v2f4a5b6c78d
Revises: t0d2a3b4c56e
Create Date: 2026-10-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'v2f4a5b6c78d'
down_revision: Union[str, Sequence[str], None] = 't0d2a3b4c56e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)

    op.create_table(
        'notifications',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', uuid,
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text()),
        sa.Column('link', sa.String(300)),
        sa.Column('actor_id', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_notifications_user_unread', 'notifications',
                    ['user_id', 'read_at'])
    op.create_index('ix_notifications_user_created', 'notifications',
                    ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_index('ix_notifications_user_unread', table_name='notifications')
    op.drop_table('notifications')
