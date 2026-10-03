"""enforce one active attendance session per user

Revision ID: 1e2db6c6af9c
Revises: 7225bc33b029
Create Date: 2026-10-03 11:50:33.622209

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e2db6c6af9c'
down_revision: Union[str, Sequence[str], None] = '7225bc33b029'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_staff_attendance_sessions_active_user",
        "staff_attendance_sessions",
        ["business_id", "user_id"],
        unique=True,
        postgresql_where=sa.text(
            "checked_out_at IS NULL"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_staff_attendance_sessions_active_user",
        table_name="staff_attendance_sessions",
    )
