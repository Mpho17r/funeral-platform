"""create branches and assign existing records to a main branch

Revision ID: d4f5b6c7e804
Revises: c3e4a5b6d703
Create Date: 2026-10-11 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f5b6c7e804'
down_revision: Union[str, Sequence[str], None] = 'c3e4a5b6d703'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables whose rows belong to a branch.
BRANCH_TABLES = ('users', 'members', 'funeral_cases', 'resources')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'branches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_main', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'NOT (is_main AND NOT is_active)',
            name='ck_branches_main_is_active',
        ),
        sa.ForeignKeyConstraint(
            ['business_id'], ['businesses.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'business_id', 'code', name='uq_branches_business_code'
        ),
    )
    op.create_index(
        op.f('ix_branches_business_id'),
        'branches', ['business_id'], unique=False,
    )
    op.create_index(
        'uq_branches_business_name',
        'branches',
        ['business_id', sa.text('lower(name)')],
        unique=True,
    )
    op.create_index(
        'uq_branches_one_main_per_business',
        'branches',
        ['business_id'],
        unique=True,
        postgresql_where=sa.text('is_main'),
    )

    for table in BRANCH_TABLES:
        op.add_column(
            table,
            sa.Column('branch_id', sa.UUID(), nullable=True),
        )
        op.create_index(
            op.f(f'ix_{table}_branch_id'),
            table, ['branch_id'], unique=False,
        )
        op.create_foreign_key(
            f'fk_{table}_branch_id',
            table, 'branches', ['branch_id'], ['id'],
        )

    # Every existing business gets a main branch, and everything that
    # already exists is placed in it, so nothing is left unassigned.
    op.execute(
        """
        INSERT INTO branches (
            id, business_id, name, code,
            is_main, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), id, 'Main Branch', 'MAIN',
            true, true, now(), now()
        FROM businesses
        """
    )

    for table in BRANCH_TABLES:
        op.execute(
            f"""
            UPDATE {table} AS t
            SET branch_id = b.id
            FROM branches AS b
            WHERE b.business_id = t.business_id
              AND b.is_main
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in BRANCH_TABLES:
        op.drop_constraint(
            f'fk_{table}_branch_id', table, type_='foreignkey'
        )
        op.drop_index(op.f(f'ix_{table}_branch_id'), table_name=table)
        op.drop_column(table, 'branch_id')

    op.drop_index(
        'uq_branches_one_main_per_business', table_name='branches'
    )
    op.drop_index('uq_branches_business_name', table_name='branches')
    op.drop_index(op.f('ix_branches_business_id'), table_name='branches')
    op.drop_table('branches')
