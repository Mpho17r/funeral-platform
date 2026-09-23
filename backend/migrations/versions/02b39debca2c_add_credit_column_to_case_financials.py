"""preserve duplicate credit migration revision

Revision ID: 02b39debca2c
Revises: c9e4b70b668f
Create Date: 2026-08-17 16:41:17.674580
"""

from typing import Sequence, Union


revision: str = "02b39debca2c"
down_revision: Union[str, Sequence[str], None] = "c9e4b70b668f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: credit was already added by the previous migration."""
    pass


def downgrade() -> None:
    """No-op: credit belongs to the previous migration."""
    pass
