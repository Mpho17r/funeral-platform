"""message delivery tracking

Revision ID: a7e9f0a1b23c
Revises: z6d8e9f0a12b
Create Date: 2026-10-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7e9f0a1b23c'
down_revision: Union[str, Sequence[str], None] = 'z6d8e9f0a12b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    t = 'communication_messages'
    op.add_column(t, sa.Column('delivery_attempts', sa.Integer(),
                               server_default=sa.text('0'), nullable=False))
    op.add_column(t, sa.Column('last_attempt_at',
                               sa.DateTime(timezone=True), nullable=True))
    op.add_column(t, sa.Column('delivery_error', sa.Text(), nullable=True))
    op.add_column(t, sa.Column('delivered_by', sa.String(20), nullable=True))
    # Messages already marked sent were sent by a person.
    op.execute("update communication_messages set delivered_by = 'manual' "
               "where status = 'sent'")


def downgrade() -> None:
    t = 'communication_messages'
    for c in ('delivered_by', 'delivery_error', 'last_attempt_at',
              'delivery_attempts'):
        op.drop_column(t, c)
