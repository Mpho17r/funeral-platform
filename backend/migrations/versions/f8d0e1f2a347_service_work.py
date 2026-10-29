"""services work like tasks: assignees, due time, completion, archive

Revision ID: f8d0e1f2a347
Revises: e7c9d0e1f236
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f8d0e1f2a347'
down_revision: Union[str, Sequence[str], None] = 'e7c9d0e1f236'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_services', sa.Column('due_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('case_services', sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('case_services', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('case_services', sa.Column('archived_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_case_services_archived_at', 'case_services', ['archived_at'])
    op.create_foreign_key('fk_case_services_archived_by_users', 'case_services', 'users',
                          ['archived_by'], ['id'], ondelete='SET NULL')
    op.create_table(
        'case_service_assignees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('service_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('case_services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('service_id', 'user_id', name='uq_case_service_assignees'),
    )
    op.create_index('ix_case_service_assignees_service_id', 'case_service_assignees', ['service_id'])
    op.create_index('ix_case_service_assignees_user_id', 'case_service_assignees', ['user_id'])
    # Services already completed keep a completion time.
    op.execute("UPDATE case_services SET completed_at = updated_at WHERE status = 'completed'")


def downgrade() -> None:
    op.drop_table('case_service_assignees')
    op.drop_constraint('fk_case_services_archived_by_users', 'case_services', type_='foreignkey')
    op.drop_index('ix_case_services_archived_at', table_name='case_services')
    for col in ('archived_by', 'archived_at', 'completed_at', 'due_at'):
        op.drop_column('case_services', col)
