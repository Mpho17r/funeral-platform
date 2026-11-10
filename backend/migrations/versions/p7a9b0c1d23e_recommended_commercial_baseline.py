"""Update seeded plan prices to the recommended commercial baseline.

Revision ID: p7a9b0c1d23e
Revises: k9c1d2e3f458

Only rows still matching the original seed values are changed. Any plan
manually customised by the platform owner is left untouched.
"""
import sqlalchemy as sa
from alembic import op

revision = "p7a9b0c1d23e"
down_revision = "k9c1d2e3f458"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # code, old base, new base, extra staff, old extra branch, new extra branch
    rows = [
        ("funeral-beginner", 80000, 89900, 6000, 6000, 14900),
        ("funeral-standard", 100000, 129900, 6000, 6000, 14900),
        ("funeral-enterprise", 180000, 249900, 6000, 6000, 14900),
        ("general-startup", 45000, 49900, 5000, 5000, 9900),
        ("general-standard", 95000, 109900, 5000, 5000, 9900),
        ("general-enterprise", 150000, 199900, 5000, 5000, 9900),
    ]
    bind = op.get_bind()
    statement = sa.text(
        """
        UPDATE pricing_plans
        SET base_price_cents = :new_base,
            extra_branch_cents = :new_branch
        WHERE code = :code
          AND base_price_cents = :old_base
          AND extra_staff_cents = :extra_staff
          AND extra_branch_cents = :old_branch
        """
    )
    for code, old_base, new_base, extra_staff, old_branch, new_branch in rows:
        bind.execute(
            statement,
            {
                "code": code,
                "old_base": old_base,
                "new_base": new_base,
                "extra_staff": extra_staff,
                "old_branch": old_branch,
                "new_branch": new_branch,
            },
        )


def downgrade() -> None:
    # Deliberately no reverse update: commercial prices may have been
    # approved or edited after this migration. Restore from a reviewed
    # backup or update the plans through Platform Admin if rollback is needed.
    pass
