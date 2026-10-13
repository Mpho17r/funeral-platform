"""create mortuary locations remains records and custody log

Revision ID: g7c8e9f0b127
Revises: f6b7d8e9a016
Create Date: 2026-10-13 11:38:21.439567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7c8e9f0b127'
down_revision: Union[str, Sequence[str], None] = 'f6b7d8e9a016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mortuary_locations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('branch_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('fridge', 'cold_room', 'preparation_room', 'chapel_of_rest', 'other')", name='ck_mortuary_locations_kind'),
    sa.CheckConstraint('capacity IS NULL OR capacity > 0', name='ck_mortuary_locations_capacity'),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mortuary_locations_branch_id'), 'mortuary_locations', ['branch_id'], unique=False)
    op.create_index(op.f('ix_mortuary_locations_business_id'), 'mortuary_locations', ['business_id'], unique=False)
    op.create_index('uq_mortuary_locations_business_name', 'mortuary_locations', ['business_id', sa.literal_column('lower(name)')], unique=True)
    op.create_table('remains_records',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('case_id', sa.UUID(), nullable=False),
    sa.Column('tag_number', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'in_custody'"), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_from_type', sa.String(length=30), nullable=False),
    sa.Column('received_from', sa.Text(), nullable=True),
    sa.Column('collected_by_name', sa.String(length=150), nullable=True),
    sa.Column('vehicle_resource_id', sa.UUID(), nullable=True),
    sa.Column('condition_notes', sa.Text(), nullable=True),
    sa.Column('belongings', sa.Text(), nullable=True),
    sa.Column('current_location_id', sa.UUID(), nullable=True),
    sa.Column('cooled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('identified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('identified_by_name', sa.String(length=150), nullable=True),
    sa.Column('identified_relationship', sa.String(length=100), nullable=True),
    sa.Column('received_by', sa.UUID(), nullable=True),
    sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('released_by', sa.UUID(), nullable=True),
    sa.Column('released_to_name', sa.String(length=150), nullable=True),
    sa.Column('released_to_id_number', sa.String(length=50), nullable=True),
    sa.Column('released_to_relationship', sa.String(length=100), nullable=True),
    sa.Column('release_override_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(status = 'released' AND released_at IS NOT NULL AND current_location_id IS NULL) OR (status = 'in_custody' AND released_at IS NULL)", name='ck_remains_records_release_state'),
    sa.CheckConstraint("received_from_type IN ('home', 'hospital', 'state_mortuary', 'scene', 'other')", name='ck_remains_records_received_from_type'),
    sa.CheckConstraint("status IN ('in_custody', 'released')", name='ck_remains_records_status'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['case_id'], ['funeral_cases.id'], ),
    sa.ForeignKeyConstraint(['current_location_id'], ['mortuary_locations.id'], ),
    sa.ForeignKeyConstraint(['received_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['released_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['vehicle_resource_id'], ['resources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'tag_number', name='uq_remains_records_business_tag'),
    sa.UniqueConstraint('case_id', name='uq_remains_records_case')
    )
    op.create_index(op.f('ix_remains_records_business_id'), 'remains_records', ['business_id'], unique=False)
    op.create_index(op.f('ix_remains_records_current_location_id'), 'remains_records', ['current_location_id'], unique=False)
    op.create_index('ix_remains_records_status', 'remains_records', ['business_id', 'status'], unique=False)
    op.create_table('custody_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('business_id', sa.UUID(), nullable=False),
    sa.Column('remains_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('from_location_id', sa.UUID(), nullable=True),
    sa.Column('to_location_id', sa.UUID(), nullable=True),
    sa.Column('procedure', sa.String(length=20), nullable=True),
    sa.Column('temperature_c', sa.Numeric(precision=4, scale=1), nullable=True),
    sa.Column('performed_by', sa.UUID(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("event_type IN ('received', 'moved', 'prepared', 'identified', 'temperature', 'released', 'note')", name='ck_custody_events_type'),
    sa.CheckConstraint("procedure IS NULL OR procedure IN ('washed', 'embalmed', 'dressed', 'other')", name='ck_custody_events_procedure'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['from_location_id'], ['mortuary_locations.id'], ),
    sa.ForeignKeyConstraint(['performed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['remains_id'], ['remains_records.id'], ),
    sa.ForeignKeyConstraint(['to_location_id'], ['mortuary_locations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custody_events_business_id'), 'custody_events', ['business_id'], unique=False)
    op.create_index('ix_custody_events_remains_time', 'custody_events', ['remains_id', 'occurred_at'], unique=False)

    # The custody log is append-only: the database itself refuses to
    # change or remove an entry, so the history of who had the
    # remains and where cannot be rewritten.
    op.execute(
        """
        CREATE FUNCTION custody_events_are_append_only()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'custody_events is append-only: % is not allowed',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER custody_events_no_update_or_delete
        BEFORE UPDATE OR DELETE ON custody_events
        FOR EACH ROW EXECUTE FUNCTION custody_events_are_append_only()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "DROP TRIGGER custody_events_no_update_or_delete "
        "ON custody_events"
    )
    op.execute("DROP FUNCTION custody_events_are_append_only()")
    op.drop_index('ix_custody_events_remains_time', table_name='custody_events')
    op.drop_index(op.f('ix_custody_events_business_id'), table_name='custody_events')
    op.drop_table('custody_events')
    op.drop_index('ix_remains_records_status', table_name='remains_records')
    op.drop_index(op.f('ix_remains_records_current_location_id'), table_name='remains_records')
    op.drop_index(op.f('ix_remains_records_business_id'), table_name='remains_records')
    op.drop_table('remains_records')
    op.drop_index('uq_mortuary_locations_business_name', table_name='mortuary_locations')
    op.drop_index(op.f('ix_mortuary_locations_business_id'), table_name='mortuary_locations')
    op.drop_index(op.f('ix_mortuary_locations_branch_id'), table_name='mortuary_locations')
    op.drop_table('mortuary_locations')
