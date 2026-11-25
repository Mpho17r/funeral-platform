"""Merge the existing VAT and billing migration branches.

Revision ID: b7c9d1e3f5a0
Revises: a1b2c3d4e5f6, v0a7b9c2d3e4
"""
from typing import Sequence, Union

revision: str = "b7c9d1e3f5a0"
down_revision: Union[str, Sequence[str], None] = (
    "a1b2c3d4e5f6",
    "v0a7b9c2d3e4",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both parent migrations have already applied their own schema/data changes.
    pass


def downgrade() -> None:
    # Downgrading this merge point returns Alembic to its two parent revisions.
    pass
