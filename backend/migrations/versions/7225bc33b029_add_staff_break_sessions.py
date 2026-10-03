"""add staff break sessions

Revision ID: 7225bc33b029
Revises: 1419f94061ec
Create Date: 2026-10-03 11:05:52.261876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7225bc33b029'
down_revision: Union[str, Sequence[str], None] = '1419f94061ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "staff_break_sessions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "attendance_session_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "break_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attendance_session_id"],
            ["staff_attendance_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_staff_break_sessions_attendance_session_id",
        "staff_break_sessions",
        ["attendance_session_id"],
    )

    op.create_index(
        "ix_staff_break_sessions_business_id",
        "staff_break_sessions",
        ["business_id"],
    )

    op.create_index(
        "ix_staff_break_sessions_user_id",
        "staff_break_sessions",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_staff_break_sessions_user_id",
        table_name="staff_break_sessions",
    )
    op.drop_index(
        "ix_staff_break_sessions_business_id",
        table_name="staff_break_sessions",
    )
    op.drop_index(
        "ix_staff_break_sessions_attendance_session_id",
        table_name="staff_break_sessions",
    )
    op.drop_table("staff_break_sessions")
