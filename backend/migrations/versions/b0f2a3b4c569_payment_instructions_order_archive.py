"""payment instructions on the portal; archive for purchase orders

Revision ID: b0f2a3b4c569
Revises: a9e1f2a3b458
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b0f2a3b4c569'
down_revision: Union[str, Sequence[str], None] = 'a9e1f2a3b458'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('payment_instructions', sa.Text(), nullable=True))
    op.add_column('purchase_orders', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_purchase_orders_archived_at', 'purchase_orders', ['archived_at'])


def downgrade() -> None:
    op.drop_index('ix_purchase_orders_archived_at', table_name='purchase_orders')
    op.drop_column('purchase_orders', 'archived_at')
    op.drop_column('businesses', 'payment_instructions')
