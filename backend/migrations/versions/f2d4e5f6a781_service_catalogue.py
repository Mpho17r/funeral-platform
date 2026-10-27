"""service catalogue and packages

Revision ID: f2d4e5f6a781
Revises: e1c3d4e5f670
Create Date: 2026-10-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f2d4e5f6a781'
down_revision: Union[str, Sequence[str], None] = 'e1c3d4e5f670'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'service_catalogue_items',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('service_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('default_quantity', sa.Integer(), nullable=False),
        sa.Column('price_varies', sa.Boolean(), nullable=False),
        sa.Column('inventory_item_id', uuid, sa.ForeignKey('inventory_items.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('default_price >= 0', name='ck_catalogue_price_non_negative'),
        sa.CheckConstraint('default_quantity >= 1', name='ck_catalogue_quantity_positive'),
        sa.UniqueConstraint('business_id', 'name', name='uq_catalogue_business_name'),
    )
    op.create_index('ix_service_catalogue_items_business_id', 'service_catalogue_items', ['business_id'])
    op.create_table(
        'service_packages',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('business_id', 'name', name='uq_package_business_name'),
    )
    op.create_index('ix_service_packages_business_id', 'service_packages', ['business_id'])
    op.create_table(
        'service_package_items',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('package_id', uuid, sa.ForeignKey('service_packages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('catalogue_item_id', uuid, sa.ForeignKey('service_catalogue_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.CheckConstraint('quantity >= 1', name='ck_package_item_quantity'),
        sa.UniqueConstraint('package_id', 'catalogue_item_id', name='uq_package_item'),
    )
    op.create_index('ix_service_package_items_business_id', 'service_package_items', ['business_id'])
    op.create_index('ix_service_package_items_package_id', 'service_package_items', ['package_id'])


def downgrade() -> None:
    op.drop_table('service_package_items')
    op.drop_table('service_packages')
    op.drop_table('service_catalogue_items')
