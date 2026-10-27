"""service catalogue and packages

Revision ID: f2d4e5f6a781
Revises: e1c3d4e5f670
Create Date: 2026-10-27 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f2d4e5f6a781'
down_revision: Union[str, Sequence[str], None] = 'e1c3d4e5f670'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        'service_catalog_items',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('default_quantity', sa.Integer, nullable=False, server_default='1'),
        sa.Column('price_varies', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('is_standard', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('inventory_item_id', UUID, sa.ForeignKey('inventory_items.id'), nullable=True),
        sa.Column('provider', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('business_id', 'name', name='uq_catalog_business_name'),
    )
    op.create_index('ix_service_catalog_items_business_id', 'service_catalog_items', ['business_id'])
    op.create_index('ix_service_catalog_items_is_active', 'service_catalog_items', ['is_active'])

    op.create_table(
        'service_packages',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('business_id', 'name', name='uq_package_business_name'),
    )
    op.create_index('ix_service_packages_business_id', 'service_packages', ['business_id'])

    op.create_table(
        'service_package_items',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('package_id', UUID, sa.ForeignKey('service_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('catalog_item_id', UUID, sa.ForeignKey('service_catalog_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False, server_default='1'),
        sa.UniqueConstraint('package_id', 'catalog_item_id', name='uq_package_item'),
    )
    op.create_index('ix_service_package_items_business_id', 'service_package_items', ['business_id'])
    op.create_index('ix_service_package_items_package_id', 'service_package_items', ['package_id'])

    op.add_column('case_services', sa.Column(
        'catalog_item_id', UUID,
        sa.ForeignKey('service_catalog_items.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('case_services', 'catalog_item_id')
    op.drop_table('service_package_items')
    op.drop_table('service_packages')
    op.drop_table('service_catalog_items')
