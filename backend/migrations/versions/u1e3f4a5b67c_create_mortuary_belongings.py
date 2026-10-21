"""Create item-level mortuary belongings register."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "u1e3f4a5b67c"
down_revision: Union[str, Sequence[str], None] = "t0d2e3f4a56b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mortuary_belongings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "remains_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("remains_records.id"),
            nullable=False,
        ),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("storage_location", sa.String(150), nullable=False),
        sa.Column("received_from", sa.String(150), nullable=True),
        sa.Column(
            "received_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("received_by_name", sa.String(150), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            server_default=sa.text("'in_safekeeping'"),
            nullable=False,
        ),
        sa.Column("returned_to_name", sa.String(150), nullable=True),
        sa.Column(
            "returned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "transferred_to_location", sa.String(150), nullable=True
        ),
        sa.Column(
            "transferred_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "transferred_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_mortuary_belongings_quantity_positive",
        ),
        sa.CheckConstraint(
            "status IN ('in_safekeeping', 'returned', 'transferred')",
            name="ck_mortuary_belongings_status",
        ),
    )

    op.create_index(
        "ix_mortuary_belongings_business_status",
        "mortuary_belongings",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_mortuary_belongings_remains",
        "mortuary_belongings",
        ["remains_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mortuary_belongings_remains",
        table_name="mortuary_belongings",
    )
    op.drop_index(
        "ix_mortuary_belongings_business_status",
        table_name="mortuary_belongings",
    )
    op.drop_table("mortuary_belongings")
