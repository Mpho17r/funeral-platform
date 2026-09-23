"""add membership cover policy settings

Revision ID: 884cf88f5aa6
Revises: 5834751af8d3
Create Date: 2026-09-15 14:13:06.662210

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision: str = "884cf88f5aa6"
down_revision: Union[str, Sequence[str], None] = "5834751af8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "businesses",
        sa.Column(
            "grace_period_days",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "cover_during_arrears",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "lapse_after_days",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "allow_reinstatement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("businesses", "allow_reinstatement")
    op.drop_column("businesses", "lapse_after_days")
    op.drop_column("businesses", "cover_during_arrears")
    op.drop_column("businesses", "grace_period_days")
