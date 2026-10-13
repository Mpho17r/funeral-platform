"""create death records and case paperwork items

Revision ID: f6b7d8e9a016
Revises: e5a6c7d8f905
Create Date: 2026-10-13 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b7d8e9a016'
down_revision: Union[str, Sequence[str], None] = 'e5a6c7d8f905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'death_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('deceased_id_type', sa.String(length=20), nullable=False),
        sa.Column('deceased_id_number', sa.String(length=50), nullable=True),
        sa.Column('time_of_death', sa.Time(), nullable=True),
        sa.Column('place_of_death_type', sa.String(length=20), nullable=True),
        sa.Column('place_of_death', sa.Text(), nullable=True),
        sa.Column('manner_of_death', sa.String(length=20), nullable=False),
        sa.Column('cause_of_death', sa.Text(), nullable=True),
        sa.Column('certifier_name', sa.String(length=150), nullable=True),
        sa.Column('forensic_status', sa.String(length=20), nullable=False),
        sa.Column('police_case_number', sa.String(length=50), nullable=True),
        sa.Column('infectious_remains', sa.Boolean(), nullable=False),
        sa.Column('disposal_method', sa.String(length=20), nullable=False),
        sa.Column('informant_name', sa.String(length=150), nullable=True),
        sa.Column(
            'informant_relationship', sa.String(length=100), nullable=True
        ),
        sa.Column('informant_phone', sa.String(length=30), nullable=True),
        sa.Column(
            'informant_id_number', sa.String(length=50), nullable=True
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.CheckConstraint(
            "manner_of_death IN ('pending', 'natural', 'unnatural')",
            name='ck_death_records_manner',
        ),
        sa.CheckConstraint(
            "forensic_status IN ('not_applicable', 'referred', "
            "'post_mortem_done', 'released')",
            name='ck_death_records_forensic_status',
        ),
        sa.CheckConstraint(
            "disposal_method IN ('burial', 'cremation', 'repatriation')",
            name='ck_death_records_disposal_method',
        ),
        sa.CheckConstraint(
            "deceased_id_type IN ('sa_id', 'passport', 'other')",
            name='ck_death_records_id_type',
        ),
        sa.CheckConstraint(
            "place_of_death_type IS NULL OR place_of_death_type IN "
            "('home', 'hospital', 'public_place', 'other')",
            name='ck_death_records_place_type',
        ),
        sa.CheckConstraint(
            "forensic_status = 'not_applicable' OR "
            "manner_of_death <> 'natural'",
            name='ck_death_records_forensic_not_natural',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id', name='uq_death_records_case'),
    )
    op.create_index(
        op.f('ix_death_records_business_id'),
        'death_records', ['business_id'], unique=False,
    )

    op.create_table(
        'case_paperwork_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('item_type', sa.String(length=40), nullable=False),
        sa.Column('label', sa.String(length=150), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('obtained_on', sa.Date(), nullable=True),
        sa.Column('obtained_by', sa.UUID(), nullable=True),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'obtained', 'not_applicable')",
            name='ck_case_paperwork_items_status',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['obtained_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['document_id'], ['case_documents.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_case_paperwork_items_business_id'),
        'case_paperwork_items', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_case_paperwork_items_case_id'),
        'case_paperwork_items', ['case_id'], unique=False,
    )
    op.create_index(
        'uq_case_paperwork_items_standard',
        'case_paperwork_items',
        ['case_id', 'item_type'],
        unique=True,
        postgresql_where=sa.text("item_type <> 'custom'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_case_paperwork_items_standard',
        table_name='case_paperwork_items',
        postgresql_where=sa.text("item_type <> 'custom'"),
    )
    op.drop_index(
        op.f('ix_case_paperwork_items_case_id'),
        table_name='case_paperwork_items',
    )
    op.drop_index(
        op.f('ix_case_paperwork_items_business_id'),
        table_name='case_paperwork_items',
    )
    op.drop_table('case_paperwork_items')

    op.drop_index(
        op.f('ix_death_records_business_id'), table_name='death_records'
    )
    op.drop_table('death_records')
