"""add business VAT registration settings

Revision ID: a7b8c9d0e123
Revises: z6d8e9f0a12b
Create Date: 2026-10-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b8c9d0e123"
down_revision: Union[str, Sequence[str], None] = "z6d8e9f0a12b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column(
            "vat_registered",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "businesses",
        sa.Column("vat_registration_number", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "prices_include_vat",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "prices_include_vat")
    op.drop_column("businesses", "vat_registration_number")
    op.drop_column("businesses", "vat_registered")
