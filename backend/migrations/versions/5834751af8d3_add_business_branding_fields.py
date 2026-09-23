"""add business branding fields

Revision ID: 5834751af8d3
Revises: fa5386596a18
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5834751af8d3"
down_revision: Union[str, Sequence[str], None] = "fa5386596a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "secondary_color",
            sa.String(length=20),
            nullable=False,
            server_default="#64748b",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "watermark_url",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "watermark_opacity",
            sa.Float(),
            nullable=False,
            server_default="0.05",
        ),
    )

    op.add_column(
        "businesses",
        sa.Column(
            "theme_preference",
            sa.String(length=20),
            nullable=False,
            server_default="system",
        ),
    )

    op.alter_column(
        "businesses",
        "secondary_color",
        server_default=None,
    )

    op.alter_column(
        "businesses",
        "watermark_opacity",
        server_default=None,
    )

    op.alter_column(
        "businesses",
        "theme_preference",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("businesses", "theme_preference")
    op.drop_column("businesses", "watermark_opacity")
    op.drop_column("businesses", "watermark_url")
    op.drop_column("businesses", "secondary_color")
