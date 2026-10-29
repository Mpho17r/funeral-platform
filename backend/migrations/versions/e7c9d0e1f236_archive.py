"""archive: finished tasks, retention settings

Revision ID: e7c9d0e1f236
Revises: d6b8c9d0e125
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7c9d0e1f236'
down_revision: Union[str, Sequence[str], None] = 'd6b8c9d0e125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_tasks', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('case_tasks', sa.Column('archived_by', sa.Uuid(), nullable=True))
    op.create_index('ix_case_tasks_archived_at', 'case_tasks', ['archived_at'])
    op.create_foreign_key(
        'fk_case_tasks_archived_by_users', 'case_tasks', 'users',
        ['archived_by'], ['id'], ondelete='SET NULL',
    )
    op.add_column('businesses', sa.Column('archive_after_days', sa.Integer(), nullable=False, server_default='14'))
    op.add_column('businesses', sa.Column('delete_archived_after_months', sa.Integer(), nullable=True))
    # Tasks finished before this release are archived straight away so the
    # working lists show only what needs attention.
    op.execute(
        "UPDATE case_tasks SET archived_at = now() "
        "WHERE status = 'completed' AND completed_at < now() - interval '14 days'"
    )


def downgrade() -> None:
    op.drop_column('businesses', 'delete_archived_after_months')
    op.drop_column('businesses', 'archive_after_days')
    op.drop_constraint('fk_case_tasks_archived_by_users', 'case_tasks', type_='foreignkey')
    op.drop_index('ix_case_tasks_archived_at', table_name='case_tasks')
    op.drop_column('case_tasks', 'archived_by')
    op.drop_column('case_tasks', 'archived_at')
