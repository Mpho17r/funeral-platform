"""add staff break expiry policy settings

Revision ID: 7be30ec99e6b
Revises: 7504fe88d072
Create Date: 2026-10-03 15:00:29.053020

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7be30ec99e6b"
down_revision: Union[str, Sequence[str], None] = "7504fe88d072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "break_expiry_behavior",
            sa.String(length=30),
            nullable=False,
            server_default="notify_and_keep_active",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "break_warning_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "break_warning_minutes",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "break_expiry_notification_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "businesses",
        "break_expiry_notification_enabled",
    )

    op.drop_column(
        "businesses",
        "break_warning_minutes",
    )

    op.drop_column(
        "businesses",
        "break_warning_enabled",
    )

    op.drop_column(
        "businesses",
        "break_expiry_behavior",
    )