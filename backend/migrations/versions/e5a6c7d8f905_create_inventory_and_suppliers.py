"""create suppliers, inventory items and stock movements

Revision ID: e5a6c7d8f905
Revises: d4f5b6c7e804
Create Date: 2026-10-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a6c7d8f905'
down_revision: Union[str, Sequence[str], None] = 'd4f5b6c7e804'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'suppliers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('contact_person', sa.String(length=150), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_suppliers_business_id'),
        'suppliers', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_suppliers_is_active'),
        'suppliers', ['is_active'], unique=False,
    )
    op.create_index(
        'uq_suppliers_business_name',
        'suppliers',
        ['business_id', sa.text('lower(name)')],
        unique=True,
    )

    op.create_table(
        'inventory_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=True),
        sa.Column('supplier_id', sa.UUID(), nullable=True),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity_on_hand', sa.Numeric(12, 2), nullable=False),
        sa.Column('reorder_level', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('coffin', 'casket', 'flowers', 'clothing', "
            "'consumable', 'stationery', 'other')",
            name='ck_inventory_items_category',
        ),
        sa.CheckConstraint(
            'quantity_on_hand >= 0',
            name='ck_inventory_items_quantity_non_negative',
        ),
        sa.CheckConstraint(
            'reorder_level >= 0',
            name='ck_inventory_items_reorder_non_negative',
        ),
        sa.CheckConstraint(
            'unit_cost IS NULL OR unit_cost >= 0',
            name='ck_inventory_items_cost_non_negative',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_inventory_items_business_id'),
        'inventory_items', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_inventory_items_branch_id'),
        'inventory_items', ['branch_id'], unique=False,
    )
    op.create_index(
        op.f('ix_inventory_items_supplier_id'),
        'inventory_items', ['supplier_id'], unique=False,
    )
    op.create_index(
        op.f('ix_inventory_items_category'),
        'inventory_items', ['category'], unique=False,
    )
    op.create_index(
        op.f('ix_inventory_items_is_active'),
        'inventory_items', ['is_active'], unique=False,
    )
    op.create_index(
        'uq_inventory_items_business_sku',
        'inventory_items', ['business_id', 'sku'], unique=True,
    )

    op.create_table(
        'stock_movements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('movement_type', sa.String(length=20), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('balance_after', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_cost', sa.Numeric(12, 2), nullable=True),
        sa.Column('supplier_id', sa.UUID(), nullable=True),
        sa.Column('case_id', sa.UUID(), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "movement_type IN ('receipt', 'issue', 'return', "
            "'adjustment')",
            name='ck_stock_movements_type',
        ),
        sa.CheckConstraint(
            'quantity <> 0',
            name='ck_stock_movements_quantity_not_zero',
        ),
        sa.CheckConstraint(
            'balance_after >= 0',
            name='ck_stock_movements_balance_non_negative',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.ForeignKeyConstraint(['case_id'], ['funeral_cases.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_stock_movements_business_id'),
        'stock_movements', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_stock_movements_movement_type'),
        'stock_movements', ['movement_type'], unique=False,
    )
    op.create_index(
        op.f('ix_stock_movements_case_id'),
        'stock_movements', ['case_id'], unique=False,
    )
    op.create_index(
        'ix_stock_movements_item_created',
        'stock_movements', ['item_id', 'created_at'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('stock_movements')
    op.drop_table('inventory_items')
    op.drop_table('suppliers')
