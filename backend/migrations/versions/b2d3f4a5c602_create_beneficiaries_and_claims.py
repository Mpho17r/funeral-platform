"""create membership beneficiaries and claims

Revision ID: b2d3f4a5c602
Revises: a1c2e3f4b501
Create Date: 2026-10-08 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3f4a5c602'
down_revision: Union[str, Sequence[str], None] = 'a1c2e3f4b501'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'membership_beneficiaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('membership_id', sa.UUID(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('relationship', sa.String(length=50), nullable=False),
        sa.Column('id_number', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('share_percent', sa.Numeric(precision=5, scale=2),
                  nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'share_percent > 0 AND share_percent <= 100',
            name='ck_membership_beneficiaries_share',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['membership_id'], ['memberships.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_membership_beneficiaries_business_id'),
        'membership_beneficiaries', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_membership_beneficiaries_membership_id'),
        'membership_beneficiaries', ['membership_id'], unique=False,
    )
    op.create_index(
        op.f('ix_membership_beneficiaries_is_active'),
        'membership_beneficiaries', ['is_active'], unique=False,
    )

    op.create_table(
        'membership_claims',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('claim_number', sa.String(length=50), nullable=False),
        sa.Column('membership_id', sa.UUID(), nullable=False),
        sa.Column('case_id', sa.UUID(), nullable=False),
        sa.Column('covered_dependent_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('claimed_amount', sa.Numeric(precision=12, scale=2),
                  nullable=False),
        sa.Column('approved_amount', sa.Numeric(precision=12, scale=2),
                  nullable=True),
        sa.Column('submission_coverage', sa.JSON(), nullable=True),
        sa.Column('decision_coverage', sa.JSON(), nullable=True),
        sa.Column('override_used', sa.Boolean(), nullable=False),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('decided_by', sa.UUID(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_by', sa.UUID(), nullable=True),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('payout_allocations', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('submitted_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', "
            "'rejected', 'paid', 'cancelled')",
            name='ck_membership_claims_status',
        ),
        sa.CheckConstraint(
            'claimed_amount > 0',
            name='ck_membership_claims_claimed_amount',
        ),
        sa.CheckConstraint(
            'approved_amount IS NULL OR approved_amount >= 0',
            name='ck_membership_claims_approved_amount',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['membership_id'], ['memberships.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['case_id'], ['funeral_cases.id'], ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['covered_dependent_id'], ['covered_dependents.id'],
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['decided_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['paid_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['submitted_by'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'business_id', 'claim_number',
            name='uq_membership_claims_business_claim_number',
        ),
    )
    op.create_index(
        op.f('ix_membership_claims_business_id'),
        'membership_claims', ['business_id'], unique=False,
    )
    op.create_index(
        op.f('ix_membership_claims_membership_id'),
        'membership_claims', ['membership_id'], unique=False,
    )
    op.create_index(
        op.f('ix_membership_claims_case_id'),
        'membership_claims', ['case_id'], unique=False,
    )
    op.create_index(
        op.f('ix_membership_claims_status'),
        'membership_claims', ['status'], unique=False,
    )
    op.create_index(
        'uq_membership_claims_one_live_per_case',
        'membership_claims',
        ['case_id'],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('submitted', 'under_review', 'approved', 'paid')"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_membership_claims_one_live_per_case',
        table_name='membership_claims',
    )
    op.drop_index(
        op.f('ix_membership_claims_status'),
        table_name='membership_claims',
    )
    op.drop_index(
        op.f('ix_membership_claims_case_id'),
        table_name='membership_claims',
    )
    op.drop_index(
        op.f('ix_membership_claims_membership_id'),
        table_name='membership_claims',
    )
    op.drop_index(
        op.f('ix_membership_claims_business_id'),
        table_name='membership_claims',
    )
    op.drop_table('membership_claims')

    op.drop_index(
        op.f('ix_membership_beneficiaries_is_active'),
        table_name='membership_beneficiaries',
    )
    op.drop_index(
        op.f('ix_membership_beneficiaries_membership_id'),
        table_name='membership_beneficiaries',
    )
    op.drop_index(
        op.f('ix_membership_beneficiaries_business_id'),
        table_name='membership_beneficiaries',
    )
    op.drop_table('membership_beneficiaries')
