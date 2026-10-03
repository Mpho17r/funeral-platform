"""enforce one active break per user

Revision ID: 7504fe88d072
Revises: 1e2db6c6af9c
Create Date: 2026-10-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7504fe88d072"
down_revision: Union[str, Sequence[str], None] = "1e2db6c6af9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_staff_break_sessions_active_user",
        "staff_break_sessions",
        ["business_id", "user_id"],
        unique=True,
        postgresql_where=sa.text(
            "ended_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_staff_break_sessions_active_user",
        table_name="staff_break_sessions",
    )
