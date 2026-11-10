"""Set platform subscription VAT to zero until Saccharum registers.

Revision ID: v0a7b9c2d3e4
Revises: k9c1d2e3f458
"""

from alembic import op
import sqlalchemy as sa

revision = "v0a7b9c2d3e4"
down_revision = "k9c1d2e3f458"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This affects Saccharum's platform subscription pricing only.
    # Tenant-level business tax settings are stored separately and untouched.
    op.execute(
        sa.text(
            "UPDATE platform_pricing "
            "SET vat_percent = 0, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = 1"
        )
    )


def downgrade() -> None:
    # Deliberately do not restore 15%: that could reintroduce VAT charges
    # while Saccharum is not registered. Reconfigure explicitly if status changes.
    pass
