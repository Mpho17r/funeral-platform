"""add chat reactions and attachments

Revision ID: q7a9d0e1f23b
Revises: p6f8c9d0e12a
Create Date: 2026-10-19 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'q7a9d0e1f23b'
down_revision: Union[str, Sequence[str], None] = 'p6f8c9d0e12a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_reactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('emoji', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('message_id', 'user_id', 'emoji',
                            name='uq_chat_reaction'),
    )
    op.create_index('ix_chat_reactions_message_id',
                    'chat_reactions', ['message_id'])

    op.create_table(
        'chat_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_conversations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('message_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chat_messages.id', ondelete='CASCADE')),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('filename', sa.String(200), nullable=False),
        sa.Column('media_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_chat_attachments_business_id',
                    'chat_attachments', ['business_id'])
    op.create_index('ix_chat_attachments_message_id',
                    'chat_attachments', ['message_id'])


def downgrade() -> None:
    op.drop_table('chat_attachments')
    op.drop_table('chat_reactions')
