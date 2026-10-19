"""add staff chat

Revision ID: p6f8c9d0e12a
Revises: o5e7b8c9d01f
Create Date: 2026-10-19 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'p6f8c9d0e12a'
down_revision: Union[str, Sequence[str], None] = 'o5e7b8c9d01f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('name', sa.String(120)),
        sa.Column('description', sa.Text()),
        sa.Column('group_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('groups.id', ondelete='SET NULL')),
        sa.Column('direct_key', sa.String(80)),
        sa.Column('created_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True),
                  nullable=False),
        sa.UniqueConstraint('business_id', 'direct_key',
                            name='uq_chat_direct_pair'),
    )
    op.create_index('ix_chat_conversations_business_id',
                    'chat_conversations', ['business_id'])

    op.create_table(
        'chat_participants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_read_at', sa.DateTime(timezone=True),
                  nullable=False),
        sa.UniqueConstraint('conversation_id', 'user_id',
                            name='uq_chat_participant'),
    )
    op.create_index('ix_chat_participants_conversation_id',
                    'chat_participants', ['conversation_id'])
    op.create_index('ix_chat_participants_user_id',
                    'chat_participants', ['user_id'])

    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('kind', sa.String(20), nullable=False,
                  server_default='text'),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('meta', postgresql.JSONB()),
        sa.Column('reply_to_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_chat_messages_business_id',
                    'chat_messages', ['business_id'])
    op.create_index('ix_chat_messages_conv_created',
                    'chat_messages', ['conversation_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('chat_messages')
    op.drop_table('chat_participants')
    op.drop_table('chat_conversations')
