"""add reinstatement policy

Revision ID: f401faf72d76
Revises: 884cf88f5aa6
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f401faf72d76"
down_revision: Union[str, Sequence[str], None] = "884cf88f5aa6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new policy column first.
    op.add_column(
        "businesses",
        sa.Column(
            "reinstatement_policy",
            sa.String(length=30),
            nullable=True,
        ),
    )

    # Preserve the meaning of the existing Boolean setting.
    op.execute(
        """
        UPDATE businesses
        SET reinstatement_policy =
            CASE
                WHEN allow_reinstatement = TRUE
                    THEN 'automatic'
                ELSE 'not_allowed'
            END
        """
    )

    # Every existing business now has an explicit policy.
    op.alter_column(
        "businesses",
        "reinstatement_policy",
        nullable=False,
    )

    # The new policy replaces the old Boolean.
    op.drop_column(
        "businesses",
        "allow_reinstatement",
    )


def downgrade() -> None:
    # Restore the old Boolean column.
    op.add_column(
        "businesses",
        sa.Column(
            "allow_reinstatement",
            sa.Boolean(),
            nullable=True,
        ),
    )

    # Automatic becomes True; all other policies become False.
    op.execute(
        """
        UPDATE businesses
        SET allow_reinstatement =
            CASE
                WHEN reinstatement_policy = 'automatic'
                    THEN TRUE
                ELSE FALSE
            END
        """
    )

    op.alter_column(
        "businesses",
        "allow_reinstatement",
        nullable=False,
    )

    op.drop_column(
        "businesses",
        "reinstatement_policy",
    )
