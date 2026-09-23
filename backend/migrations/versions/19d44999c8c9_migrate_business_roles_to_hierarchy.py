"""migrate business roles to hierarchy

Revision ID: 19d44999c8c9

Revises: 127a9c360381

Create Date: 2026-09-05 13:05:36.725958

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision: str = "19d44999c8c9"
down_revision: Union[str, Sequence[str], None] = "127a9c360381"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate legacy business roles to the new hierarchy."""

    users = sa.table(
        "users",
        sa.column("role", sa.String()),
    )

    op.execute(
        users.update()
        .where(users.c.role == "admin")
        .values(role="main_admin")
    )

    op.execute(
        users.update()
        .where(users.c.role == "manager")
        .values(role="manager")
    )


def downgrade() -> None:
    """Restore legacy admin role."""

    users = sa.table(
        "users",
        sa.column("role", sa.String()),
    )

    op.execute(
        users.update()
        .where(users.c.role == "main_admin")
        .values(role="admin")
    )
