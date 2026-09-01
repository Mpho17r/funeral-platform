"""add unique payment reference per business

Revision ID: 127a9c360381
Revises: 7052ea87ce0a
Create Date: 2026-08-20 21:24:00
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "127a9c360381"
down_revision: Union[str, Sequence[str], None] = "7052ea87ce0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique payment reference per business."""

    op.create_unique_constraint(
        "uq_case_payments_business_reference",
        "case_payments",
        ["business_id", "reference"],
    )


def downgrade() -> None:
    """Remove unique payment reference constraint."""

    op.drop_constraint(
        "uq_case_payments_business_reference",
        "case_payments",
        type_="unique",
    )
