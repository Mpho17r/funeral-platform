"""password reset and email verification

Revision ID: i7a9b0c1d236
Revises: h6f8a9b0c125
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "i7a9b0c1d236"
down_revision = "h6f8a9b0c125"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # People who already use the system are not asked to verify.
    op.execute("UPDATE users SET email_verified_at = now() WHERE email_verified_at IS NULL")

    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose"]
    )


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_column("users", "email_verified_at")
