"""add credit to case financials

Revision ID: c9e4b70b668f
Revises: 7cea49bcda82
Create Date: 2026-08-17 16:31:18.809867

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9e4b70b668f"
down_revision: Union[str, Sequence[str], None] = "7cea49bcda82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_financials",
        sa.Column(
            "credit",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
    )

    op.alter_column(
        "case_financials",
        "credit",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "case_financials",
        "credit",
    )
