"""add staff attendance sessions

Revision ID: 1419f94061ec
Revises: 3030ed6401ce
Create Date: 2026-10-03 11:00:01.665106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1419f94061ec'
down_revision: Union[str, Sequence[str], None] = '3030ed6401ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "staff_attendance_sessions",
        sa.Column(
            "id",
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
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "checked_in_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "checked_out_at",
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
        "ix_staff_attendance_sessions_business_id",
        "staff_attendance_sessions",
        ["business_id"],
    )

    op.create_index(
        "ix_staff_attendance_sessions_user_id",
        "staff_attendance_sessions",
        ["user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_staff_attendance_sessions_user_id",
        table_name="staff_attendance_sessions",
    )
    op.drop_index(
        "ix_staff_attendance_sessions_business_id",
        table_name="staff_attendance_sessions",
    )
    op.drop_table("staff_attendance_sessions")
