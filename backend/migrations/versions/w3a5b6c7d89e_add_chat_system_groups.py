"""add automatic workspace groups

Revision ID: w3a5b6c7d89e
Revises: v2f4a5b6c78d
Create Date: 2026-10-23 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'w3a5b6c7d89e'
down_revision: Union[str, Sequence[str], None] = 'v2f4a5b6c78d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_conversations',
        sa.Column('system_key', sa.String(60), nullable=True),
    )
    op.create_unique_constraint(
        'uq_chat_system_group',
        'chat_conversations',
        ['business_id', 'system_key'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_chat_system_group', 'chat_conversations', type_='unique'
    )
    op.drop_column('chat_conversations', 'system_key')
