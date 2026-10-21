"""add mortuary temperature readings

Revision ID: s9c1f2a3b45d
Revises: r8b0e1f2a34c
Create Date: 2026-10-21 05:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 's9c1f2a3b45d'
down_revision: Union[str, Sequence[str], None] = 'r8b0e1f2a34c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mortuary_temperature_readings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('business_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('mortuary_locations.id',
                                ondelete='CASCADE'),
                  nullable=False),
        sa.Column('temperature_c', sa.Numeric(4, 1), nullable=False),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('recorded_at', sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column('notes', sa.Text()),
    )
    op.create_index('ix_mortuary_temperature_readings_business_id',
                    'mortuary_temperature_readings', ['business_id'])
    op.create_index('ix_mortuary_temp_location_time',
                    'mortuary_temperature_readings',
                    ['location_id', 'recorded_at'])


def downgrade() -> None:
    op.drop_table('mortuary_temperature_readings')
