"""create resources and resource bookings

Revision ID: a1c2e3f4b501
Revises: 37c079fc2ac0
Create Date: 2026-10-08 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e3f4b501'
down_revision: Union[str, Sequence[str], None] = '37c079fc2ac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'resources',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('resource_type', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('identifier', sa.String(length=100), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resource_type IN ('vehicle', 'venue', 'equipment')",
            name='ck_resources_resource_type',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_resources_business_id'),
        'resources', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_resources_resource_type'),
        'resources', ['resource_type'], unique=False,
    )
    op.create_index(
        op.f('ix_resources_is_active'),
        'resources', ['is_active'], unique=False,
    )
    op.create_index(
        'uq_resources_business_type_identifier',
        'resources',
        ['business_id', 'resource_type', 'identifier'],
        unique=True,
        postgresql_where=sa.text('identifier IS NOT NULL'),
    )

    op.create_table(
        'resource_bookings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('resource_id', sa.UUID(), nullable=False),
        sa.Column('driver_user_id', sa.UUID(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('purpose', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'ends_at > starts_at',
            name='ck_resource_bookings_window',
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'completed', 'cancelled')",
            name='ck_resource_bookings_status',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['resource_id'], ['resources.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['driver_user_id'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_resource_bookings_business_id'),
        'resource_bookings', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_resource_bookings_case_id'),
        'resource_bookings', ['case_id'], unique=False,
    )
    op.create_index(
        op.f('ix_resource_bookings_status'),
        'resource_bookings', ['status'], unique=False,
    )
    op.create_index(
        'ix_resource_bookings_resource_window',
        'resource_bookings',
        ['resource_id', 'starts_at', 'ends_at'],
        unique=False,
    )
    op.create_index(
        'ix_resource_bookings_driver_window',
        'resource_bookings',
        ['driver_user_id', 'starts_at', 'ends_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_resource_bookings_driver_window',
        table_name='resource_bookings',
    )
    op.drop_index(
        'ix_resource_bookings_resource_window',
        table_name='resource_bookings',
    )
    op.drop_index(
        op.f('ix_resource_bookings_status'),
        table_name='resource_bookings',
    )
    op.drop_index(
        op.f('ix_resource_bookings_case_id'),
        table_name='resource_bookings',
    )
    op.drop_index(
        op.f('ix_resource_bookings_business_id'),
        table_name='resource_bookings',
    )
    op.drop_table('resource_bookings')

    op.drop_index(
        'uq_resources_business_type_identifier',
        table_name='resources',
    )
    op.drop_index(op.f('ix_resources_is_active'), table_name='resources')
    op.drop_index(op.f('ix_resources_resource_type'), table_name='resources')
    op.drop_index(op.f('ix_resources_business_id'), table_name='resources')
    op.drop_table('resources')
