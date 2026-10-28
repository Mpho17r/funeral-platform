"""Tasks: due time, shared assignees, reports and files

Revision ID: d6b8c9d0e125
Revises: c5a7b8c9d014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'd6b8c9d0e125'
down_revision: Union[str, Sequence[str], None] = 'c5a7b8c9d014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_tasks', sa.Column('due_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'case_task_assignees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('case_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('task_id', 'user_id', name='uq_task_assignee'),
    )
    op.create_index('ix_case_task_assignees_task_id', 'case_task_assignees', ['task_id'])
    op.create_index('ix_case_task_assignees_user_id', 'case_task_assignees', ['user_id'])
    op.create_table(
        'case_task_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('case_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('file_name', sa.String(255), nullable=True),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('file_path', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_case_task_entries_task_id', 'case_task_entries', ['task_id'])
    # Everyone already assigned becomes an assignee row.
    op.execute(
        "INSERT INTO case_task_assignees (id, task_id, user_id, created_at) "
        "SELECT gen_random_uuid(), id, assigned_to, now() FROM case_tasks "
        "WHERE assigned_to IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table('case_task_entries')
    op.drop_table('case_task_assignees')
    op.drop_column('case_tasks', 'due_at')
