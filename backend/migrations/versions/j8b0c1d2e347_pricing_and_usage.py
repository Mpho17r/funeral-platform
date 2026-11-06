"""pricing and usage snapshots

Revision ID: j8b0c1d2e347
Revises: i7a9b0c1d236
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j8b0c1d2e347"
down_revision = "i7a9b0c1d236"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_pricing",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("base_price_cents", sa.Integer, nullable=False),
        sa.Column("included_staff", sa.Integer, nullable=False),
        sa.Column("included_branches", sa.Integer, nullable=False),
        sa.Column("extra_staff_cents", sa.Integer, nullable=False),
        sa.Column("extra_branch_cents", sa.Integer, nullable=False),
        sa.Column("price_note", sa.String(200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Starting prices. The base price and what it includes are placeholders
    # for the platform owner to set; R25 per extra staff / branch is agreed.
    op.execute(
        """
        INSERT INTO platform_pricing
          (id, currency, base_price_cents, included_staff, included_branches,
           extra_staff_cents, extra_branch_cents, price_note, updated_at)
        VALUES (1, 'ZAR', 29900, 5, 1, 2500, 2500, NULL, now())
        """
    )

    op.create_table(
        "usage_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("staff", sa.Integer, nullable=False),
        sa.Column("branches", sa.Integer, nullable=False),
        sa.UniqueConstraint("business_id", "day", name="uq_usage_snapshot_day"),
    )
    op.create_index("ix_usage_snapshots_business_id", "usage_snapshots", ["business_id"])

    op.add_column(
        "businesses",
        sa.Column("base_price_override_cents", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "base_price_override_cents")
    op.drop_index("ix_usage_snapshots_business_id", table_name="usage_snapshots")
    op.drop_table("usage_snapshots")
    op.drop_table("platform_pricing")
