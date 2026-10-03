"""add staff attendance policy settings

Revision ID: 3030ed6401ce
Revises: e6798d96b247
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3030ed6401ce"
down_revision: Union[str, Sequence[str], None] = "e6798d96b247"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "tea_break_minutes",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "lunch_break_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "idle_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "idle_timeout_minutes")
    op.drop_column("businesses", "lunch_break_minutes")
    op.drop_column("businesses", "tea_break_minutes")
