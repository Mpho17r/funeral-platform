"""add waiting periods, plan change tracking and unnatural cause

Revision ID: i9e0a1b2d349
Revises: h8d9f0a1c238
Create Date: 2026-10-14 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i9e0a1b2d349'
down_revision: Union[str, Sequence[str], None] = 'h8d9f0a1c238'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WAITING_COLUMNS = (
    'waiting_natural_months',
    'waiting_accidental_months',
    'waiting_suicide_months',
    'waiting_upgrade_months',
)


def upgrade() -> None:
    """Upgrade schema."""
    for column in WAITING_COLUMNS:
        op.add_column(
            'membership_plans',
            sa.Column(
                column,
                sa.Integer(),
                nullable=False,
                server_default=sa.text('0'),
            ),
        )

    op.create_check_constraint(
        'ck_membership_plans_waiting_months',
        'membership_plans',
        'waiting_natural_months BETWEEN 0 AND 60 AND '
        'waiting_accidental_months BETWEEN 0 AND 60 AND '
        'waiting_suicide_months BETWEEN 0 AND 60 AND '
        'waiting_upgrade_months BETWEEN 0 AND 60',
    )

    op.add_column(
        'memberships',
        sa.Column('previous_plan_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'memberships',
        sa.Column('plan_changed_at', sa.Date(), nullable=True),
    )
    op.create_foreign_key(
        'fk_memberships_previous_plan_id',
        'memberships',
        'membership_plans',
        ['previous_plan_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.add_column(
        'death_records',
        sa.Column('unnatural_cause', sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        'ck_death_records_unnatural_cause',
        'death_records',
        "unnatural_cause IS NULL OR unnatural_cause IN "
        "('accident', 'suicide', 'homicide', 'undetermined')",
    )
    op.create_check_constraint(
        'ck_death_records_cause_needs_unnatural',
        'death_records',
        "unnatural_cause IS NULL OR manner_of_death = 'unnatural'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_death_records_cause_needs_unnatural',
        'death_records',
        type_='check',
    )
    op.drop_constraint(
        'ck_death_records_unnatural_cause',
        'death_records',
        type_='check',
    )
    op.drop_column('death_records', 'unnatural_cause')

    op.drop_constraint(
        'fk_memberships_previous_plan_id',
        'memberships',
        type_='foreignkey',
    )
    op.drop_column('memberships', 'plan_changed_at')
    op.drop_column('memberships', 'previous_plan_id')

    op.drop_constraint(
        'ck_membership_plans_waiting_months',
        'membership_plans',
        type_='check',
    )

    for column in reversed(WAITING_COLUMNS):
        op.drop_column('membership_plans', column)
