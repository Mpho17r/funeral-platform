"""inventory automation: linked service lines, reorder settings, orders

Revision ID: d0b2c3d4e56f
Revises: c9a1b2c3d45e
Create Date: 2026-10-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd0b2c3d4e56f'
down_revision: Union[str, Sequence[str], None] = 'c9a1b2c3d45e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.add_column('case_services', sa.Column(
        'inventory_item_id', uuid,
        sa.ForeignKey('inventory_items.id'), nullable=True))
    op.add_column('case_services', sa.Column(
        'stock_issued', sa.Integer(), server_default=sa.text('0'),
        nullable=False))

    op.add_column('inventory_items', sa.Column(
        'reorder_quantity', sa.Numeric(12, 2), nullable=True))
    op.add_column('inventory_items', sa.Column(
        'auto_order', sa.Boolean(), server_default=sa.text('false'),
        nullable=False))
    op.add_column('inventory_items', sa.Column(
        'low_stock_alerted_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'purchase_orders',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('branch_id', uuid, sa.ForeignKey('branches.id')),
        sa.Column('number', sa.String(30), nullable=False),
        sa.Column('item_id', uuid,
                  sa.ForeignKey('inventory_items.id'), nullable=False),
        sa.Column('supplier_id', uuid,
                  sa.ForeignKey('suppliers.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('automatic', sa.Boolean(), server_default=sa.text('false'),
                  nullable=False),
        sa.Column('send_error', sa.Text()),
        sa.Column('created_by', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('received_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('to_send', 'sent', 'received', 'cancelled')",
            name='ck_purchase_orders_status'),
        sa.CheckConstraint('quantity > 0', name='ck_purchase_orders_quantity'),
    )
    for col in ('business_id', 'branch_id', 'item_id'):
        op.create_index(f'ix_purchase_orders_{col}', 'purchase_orders', [col])
    op.create_index(
        'uq_purchase_orders_one_open_per_item', 'purchase_orders',
        ['item_id'], unique=True,
        postgresql_where=sa.text("status IN ('to_send', 'sent')"))


def downgrade() -> None:
    op.drop_table('purchase_orders')
    for c in ('low_stock_alerted_at', 'auto_order', 'reorder_quantity'):
        op.drop_column('inventory_items', c)
    op.drop_column('case_services', 'stock_issued')
    op.drop_column('case_services', 'inventory_item_id')
