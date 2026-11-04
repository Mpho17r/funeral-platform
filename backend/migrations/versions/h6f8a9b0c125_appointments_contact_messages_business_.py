"""appointments, contact messages, business documents

Revision ID: h6f8a9b0c125
Revises: g5e7f8a9b014
Create Date: 2026-11-03 12:35:34.335624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h6f8a9b0c125'
down_revision: Union[str, Sequence[str], None] = 'g5e7f8a9b014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('businesses', sa.Column('appointment_reminders', sa.Boolean(), server_default='false', nullable=False))
    op.create_table('appointments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('branch_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=15), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=True),
    sa.Column('contact_name', sa.String(length=200), nullable=True),
    sa.Column('contact_phone', sa.String(length=50), nullable=True),
    sa.Column('contact_email', sa.String(length=255), nullable=True),
    sa.Column('location', sa.String(length=300), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('assigned_user_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('cancel_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')", name='ck_appointments_status'),
    sa.CheckConstraint('end_at > start_at', name='ck_appointments_times'),
    sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_appointments_assignee_start', 'appointments', ['assigned_user_id', 'start_at'], unique=False)
    op.create_index(op.f('ix_appointments_business_id'), 'appointments', ['business_id'], unique=False)
    op.create_index('ix_appointments_business_start', 'appointments', ['business_id', 'start_at'], unique=False)
    op.create_table('business_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('expires_on', sa.Date(), nullable=True),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_name', sa.String(length=100), nullable=False),
    sa.Column('uploaded_by', sa.UUID(), nullable=True),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("category IN ('contract', 'receipt', 'invoice', 'licence', 'policy', 'identity', 'other')", name='ck_business_documents_category'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_business_documents_business_id'), 'business_documents', ['business_id'], unique=False)
    op.create_index(op.f('ix_business_documents_expires_on'), 'business_documents', ['expires_on'], unique=False)
    op.create_table('contact_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=True),
    sa.Column('appointment_id', sa.UUID(), nullable=True),
    sa.Column('recipient_name', sa.String(length=200), nullable=True),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('recipient', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('dedupe_key', sa.String(length=150), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_by', sa.UUID(), nullable=True),
    sa.Column('delivery_attempts', sa.Integer(), nullable=False),
    sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivery_error', sa.Text(), nullable=True),
    sa.Column('delivered_by', sa.String(length=20), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("channel IN ('whatsapp', 'sms', 'email')", name='ck_contact_messages_channel'),
    sa.CheckConstraint("kind IN ('custom', 'appointment_confirmation', 'appointment_reminder')", name='ck_contact_messages_kind'),
    sa.CheckConstraint("status IN ('queued', 'sent', 'cancelled')", name='ck_contact_messages_status'),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['sent_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_messages_appointment_id'), 'contact_messages', ['appointment_id'], unique=False)
    op.create_index(op.f('ix_contact_messages_business_id'), 'contact_messages', ['business_id'], unique=False)
    op.create_index('ix_contact_messages_queue', 'contact_messages', ['business_id', 'status', 'created_at'], unique=False)
    op.create_index('uq_contact_messages_dedupe', 'contact_messages', ['business_id', 'dedupe_key'], unique=True, postgresql_where='dedupe_key IS NOT NULL')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('uq_contact_messages_dedupe', table_name='contact_messages', postgresql_where='dedupe_key IS NOT NULL')
    op.drop_index('ix_contact_messages_queue', table_name='contact_messages')
    op.drop_index(op.f('ix_contact_messages_business_id'), table_name='contact_messages')
    op.drop_index(op.f('ix_contact_messages_appointment_id'), table_name='contact_messages')
    op.drop_table('contact_messages')
    op.drop_index(op.f('ix_business_documents_expires_on'), table_name='business_documents')
    op.drop_index(op.f('ix_business_documents_business_id'), table_name='business_documents')
    op.drop_table('business_documents')
    op.drop_index('ix_appointments_business_start', table_name='appointments')
    op.drop_index(op.f('ix_appointments_business_id'), table_name='appointments')
    op.drop_index('ix_appointments_assignee_start', table_name='appointments')
    op.drop_table('appointments')
    op.drop_column('businesses', 'appointment_reminders')
    # ### end Alembic commands ###
