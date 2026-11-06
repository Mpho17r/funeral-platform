"""pricing plans per kind of business, with VAT

Revision ID: k9c1d2e3f458
Revises: j8b0c1d2e347
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "k9c1d2e3f458"
down_revision = "j8b0c1d2e347"
branch_labels = None
depends_on = None

# (type, code, name, tagline, base, staff, branches, extra staff, extra branch)
# Prices are cents and exclude VAT. Funeral Beginner / Standard and general
# Startup / Standard are the agreed figures; the rest are placeholders.
PLANS = [
    ("funeral", "funeral-beginner", "Beginner", "For a funeral home just starting out", 80000, 5, 1, 6000, 6000),
    ("funeral", "funeral-standard", "Standard", "For an established funeral home", 100000, 7, 2, 6000, 6000),
    ("funeral", "funeral-enterprise", "Enterprise", "For a larger funeral business", 180000, 15, 5, 6000, 6000),
    ("general", "general-startup", "Startup", "For a small business just starting out", 45000, 3, 1, 5000, 5000),
    ("general", "general-standard", "Standard", "For an established business", 95000, 6, 2, 5000, 5000),
    ("general", "general-enterprise", "Enterprise", "For a larger business", 150000, 12, 5, 5000, 5000),
]


def upgrade() -> None:
    plans = op.create_table(
        "pricing_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("business_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("tagline", sa.String(160), nullable=True),
        sa.Column("base_price_cents", sa.Integer, nullable=False),
        sa.Column("included_staff", sa.Integer, nullable=False),
        sa.Column("included_branches", sa.Integer, nullable=False),
        sa.Column("extra_staff_cents", sa.Integer, nullable=False),
        sa.Column("extra_branch_cents", sa.Integer, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_pricing_plans_business_type", "pricing_plans", ["business_type"])
    op.bulk_insert(
        plans,
        [
            dict(
                id=uuid.uuid4(), business_type=t, code=c, name=n, tagline=tg,
                base_price_cents=b, included_staff=s, included_branches=br,
                extra_staff_cents=xs, extra_branch_cents=xb, sort_order=i, is_active=True,
            )
            for i, (t, c, n, tg, b, s, br, xs, xb) in enumerate(PLANS)
        ],
    )

    op.add_column(
        "platform_pricing",
        sa.Column("vat_percent", sa.Integer, nullable=False, server_default="15"),
    )
    for column in (
        "base_price_cents", "included_staff", "included_branches",
        "extra_staff_cents", "extra_branch_cents",
    ):
        op.drop_column("platform_pricing", column)

    op.add_column(
        "businesses",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricing_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("businesses", "plan_id")
    for column, default in (
        ("base_price_cents", "29900"), ("included_staff", "5"),
        ("included_branches", "1"), ("extra_staff_cents", "2500"),
        ("extra_branch_cents", "2500"),
    ):
        op.add_column(
            "platform_pricing",
            sa.Column(column, sa.Integer, nullable=False, server_default=default),
        )
    op.drop_column("platform_pricing", "vat_percent")
    op.drop_index("ix_pricing_plans_business_type", table_name="pricing_plans")
    op.drop_table("pricing_plans")
