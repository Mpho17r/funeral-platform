"""partner drivers, vehicles and transport jobs

Revision ID: a3e5f6b7c892
Revises: f2d4e5f6a781
Create Date: 2026-10-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3e5f6b7c892'
down_revision: Union[str, Sequence[str], None] = 'f2d4e5f6a781'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        'partner_drivers',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50)),
        sa.Column('email', sa.String(255)),
        sa.Column('area', sa.String(100)),
        sa.Column('notes', sa.Text()),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('token_hash', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_partner_drivers_business_id', 'partner_drivers', ['business_id'])
    op.create_index('ix_partner_drivers_token_hash', 'partner_drivers', ['token_hash'])

    op.create_table(
        'partner_vehicles',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('driver_id', UUID, sa.ForeignKey('partner_drivers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('make', sa.String(100)),
        sa.Column('model', sa.String(100)),
        sa.Column('vehicle_type', sa.String(50), nullable=False),
        sa.Column('colour', sa.String(50), nullable=False),
        sa.Column('registration', sa.String(30)),
        sa.Column('seats', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.CheckConstraint('seats >= 1', name='ck_partner_vehicle_seats'),
    )
    op.create_index('ix_partner_vehicles_business_id', 'partner_vehicles', ['business_id'])
    op.create_index('ix_partner_vehicles_driver_id', 'partner_vehicles', ['driver_id'])

    op.create_table(
        'transport_jobs',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('business_id', UUID, sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('case_id', UUID, sa.ForeignKey('funeral_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('required_colour', sa.String(50)),
        sa.Column('required_type', sa.String(50)),
        sa.Column('required_model', sa.String(100)),
        sa.Column('report_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('pickup_address', sa.Text()),
        sa.Column('venue', sa.String(255)),
        sa.Column('destination', sa.String(255)),
        sa.Column('dress_code', sa.String(255)),
        sa.Column('instructions', sa.Text()),
        sa.Column('pay_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('driver_id', UUID, sa.ForeignKey('partner_drivers.id')),
        sa.Column('vehicle_id', UUID, sa.ForeignKey('partner_vehicles.id')),
        sa.Column('declined_by', postgresql.JSONB(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True)),
        sa.Column('responded_at', sa.DateTime(timezone=True)),
        sa.Column('alerted_at', sa.DateTime(timezone=True)),
        sa.Column('alert_error', sa.String(255)),
        sa.Column('reminder_sent_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('expense_id', UUID, sa.ForeignKey('expenses.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('open','assigned','accepted','completed','cancelled')", name='ck_transport_jobs_status'),
        sa.CheckConstraint('pay_amount >= 0', name='ck_transport_jobs_pay'),
    )
    op.create_index('ix_transport_jobs_business_id', 'transport_jobs', ['business_id'])
    op.create_index('ix_transport_jobs_case_id', 'transport_jobs', ['case_id'])
    op.create_index('ix_transport_jobs_report_time', 'transport_jobs', ['report_time'])
    op.create_index('ix_transport_jobs_status', 'transport_jobs', ['status'])


def downgrade() -> None:
    op.drop_table('transport_jobs')
    op.drop_table('partner_vehicles')
    op.drop_table('partner_drivers')
