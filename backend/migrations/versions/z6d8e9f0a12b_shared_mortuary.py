"""shared mortuary: authorised branch links

Revision ID: z6d8e9f0a12b
Revises: y5c7d8e9f01a
Create Date: 2026-10-25 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'z6d8e9f0a12b'
down_revision: Union[str, Sequence[str], None] = 'y5c7d8e9f01a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'mortuary_location_branches',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('location_id', uuid,
                  sa.ForeignKey('mortuary_locations.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('branch_id', uuid,
                  sa.ForeignKey('branches.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('location_id', 'branch_id',
                            name='uq_mortuary_location_branches'),
    )
    for col in ('business_id', 'location_id', 'branch_id'):
        op.create_index(
            f'ix_mortuary_location_branches_{col}',
            'mortuary_location_branches', [col])


def downgrade() -> None:
    op.drop_table('mortuary_location_branches')
