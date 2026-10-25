"""add compliance register and remains viewings

Revision ID: y5c7d8e9f01a
Revises: x4b6c7d8e90f
Create Date: 2026-10-24 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'y5c7d8e9f01a'
down_revision: Union[str, Sequence[str], None] = 'x4b6c7d8e90f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    now = sa.text('now()')

    op.create_table(
        'compliance_items',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('branch_id', uuid,
                  sa.ForeignKey('branches.id', ondelete='SET NULL')),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('reference', sa.String(100)),
        sa.Column('issued_on', sa.Date()),
        sa.Column('expires_on', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='active'),
        sa.Column('created_by', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=now),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=now),
    )
    op.create_index('ix_compliance_items_business_id', 'compliance_items',
                    ['business_id'])

    op.create_table(
        'remains_viewings',
        sa.Column('id', uuid, primary_key=True),
        sa.Column('business_id', uuid,
                  sa.ForeignKey('businesses.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('case_id', uuid,
                  sa.ForeignKey('funeral_cases.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False,
                  server_default='30'),
        sa.Column('room', sa.String(100)),
        sa.Column('visitor_name', sa.String(150)),
        sa.Column('expected_visitors', sa.Integer()),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False,
                  server_default='scheduled'),
        sa.Column('cancel_reason', sa.String(300)),
        sa.Column('created_by', uuid,
                  sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=now),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=now),
    )
    op.create_index('ix_remains_viewings_case_id', 'remains_viewings',
                    ['case_id'])
    op.create_index('ix_viewings_business_start', 'remains_viewings',
                    ['business_id', 'starts_at'])


def downgrade() -> None:
    op.drop_table('remains_viewings')
    op.drop_table('compliance_items')
