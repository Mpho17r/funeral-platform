"""Merge LINDA billing and frontend redesign migration histories.

Revision ID: c8d2e4f6a1b3
Revises: b7c9d1e3f5a0, m2c4e6a8b0d1
"""

from typing import Sequence, Union

revision: str = "c8d2e4f6a1b3"

down_revision: Union[str, Sequence[str], None] = (
    "b7c9d1e3f5a0",
    "m2c4e6a8b0d1",
)

branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
