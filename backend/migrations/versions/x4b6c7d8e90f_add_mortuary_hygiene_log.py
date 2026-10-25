"""add mortuary hygiene log

Revision ID: x4b6c7d8e90f
Revises: w3a5b6c7d89e
Create Date: 2026-10-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'x4b6c7d8e90f'
down_revision: Union[str, Sequence[str], None] = 'w3a5b6c7d89e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        'mortuary_hygiene_logs',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('task', sa.String(30), nullable=False),
        sa.Column('remains_id', uuid,
                  sa.ForeignKey('remains_records.id', ondelete='SET NULL')),
        sa.Column('performed_by', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('performed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text()),
    )
    op.create_index(
        'ix_mortuary_hygiene_logs_business_id',
        'mortuary_hygiene_logs', ['business_id'],
    )
    op.create_index(
        'ix_mortuary_hygiene_logs_performed_at',
        'mortuary_hygiene_logs', ['performed_at'],
    )


def downgrade() -> None:
    op.drop_table('mortuary_hygiene_logs')
