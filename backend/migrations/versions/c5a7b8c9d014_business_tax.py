"""business tax settings

Revision ID: c5a7b8c9d014
Revises: b4f6a7c8d903
Create Date: 2026-10-28 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5a7b8c9d014'
down_revision: Union[str, Sequence[str], None] = 'b4f6a7c8d903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('tax_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('businesses', sa.Column('tax_name', sa.String(20), nullable=False, server_default='VAT'))
    op.add_column('businesses', sa.Column('tax_rate', sa.Numeric(5, 2), nullable=False, server_default='15.00'))
    # Existing businesses start with South Africa's VAT on; the main admin
    # can change or switch it off in Settings. Issued documents never change.
    op.execute("UPDATE businesses SET tax_enabled = true")


def downgrade() -> None:
    op.drop_column('businesses', 'tax_rate')
    op.drop_column('businesses', 'tax_name')
    op.drop_column('businesses', 'tax_enabled')
