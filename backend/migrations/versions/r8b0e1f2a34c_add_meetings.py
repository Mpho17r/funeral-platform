"""add meetings

Revision ID: r8b0e1f2a34c
Revises: q7a9d0e1f23b
Create Date: 2026-10-19 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'r8b0e1f2a34c'
down_revision: Union[str, Sequence[str], None] = 'q7a9d0e1f23b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meetings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('organizer_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id',
                                ondelete='SET NULL')),
        sa.Column('title', sa.String(150), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('join_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_meetings_business_id', 'meetings', ['business_id'])
    op.create_index('ix_meetings_starts_at', 'meetings', ['starts_at'])

    op.create_table(
        'meeting_invitees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('meetings.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('response', sa.String(10), nullable=False,
                  server_default='pending'),
        sa.UniqueConstraint('meeting_id', 'user_id',
                            name='uq_meeting_invitee'),
    )
    op.create_index('ix_meeting_invitees_meeting_id',
                    'meeting_invitees', ['meeting_id'])
    op.create_index('ix_meeting_invitees_user_id',
                    'meeting_invitees', ['user_id'])


def downgrade() -> None:
    op.drop_table('meeting_invitees')
    op.drop_table('meetings')
