"""add case archival fields

Revision ID: 37c079fc2ac0
Revises: 695f3ad0dbc6
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "37c079fc2ac0"
down_revision: Union[str, Sequence[str], None] = "695f3ad0dbc6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funeral_cases",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "funeral_cases",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "funeral_cases",
        sa.Column(
            "archived_by",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_funeral_cases_archived_by_users",
        "funeral_cases",
        "users",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_funeral_cases_is_archived",
        "funeral_cases",
        ["is_archived"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_funeral_cases_is_archived",
        table_name="funeral_cases",
    )

    op.drop_constraint(
        "fk_funeral_cases_archived_by_users",
        "funeral_cases",
        type_="foreignkey",
    )

    op.drop_column("funeral_cases", "archived_by")
    op.drop_column("funeral_cases", "archived_at")
    op.drop_column("funeral_cases", "is_archived")
