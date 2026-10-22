"""Add named custody handover participants.

Revision ID: t0d2e3f4a56b
Revises: s9c1f2a3b45d
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t0d2e3f4a56b"
down_revision: Union[str, Sequence[str], None] = "s9c1f2a3b45d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "custody_events",
        sa.Column("handed_over_by_name", sa.String(150), nullable=True),
    )
    op.add_column(
        "custody_events",
        sa.Column("accepted_by_name", sa.String(150), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("custody_events", "accepted_by_name")
    op.drop_column("custody_events", "handed_over_by_name")
