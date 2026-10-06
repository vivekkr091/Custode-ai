"""add_executions

Revision ID: 0011_add_executions
Revises: 0010_add_approvals
Create Date: 2026-09-29 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0011_add_executions'
down_revision: Union[str, None] = '0010_add_approvals'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'executions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('tool_id', sa.Uuid(), nullable=False),
        sa.Column('operation_id', sa.Uuid(), nullable=False),
        sa.Column('decision_id', sa.Uuid(), nullable=True),
        sa.Column('approval_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column(
            'result',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=True,
        ),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['operation_id'], ['tool_operations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approval_id'], ['approval_requests.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_executions_organization_id', 'executions', ['organization_id'], unique=False)
    op.create_index('ix_executions_runtime_action_id', 'executions', ['runtime_action_id'], unique=False)
    op.create_index('ix_executions_org_status', 'executions', ['organization_id', 'status'], unique=False)
    op.create_index('ix_executions_org_created_at', 'executions', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_executions_org_created_at', table_name='executions')
    op.drop_index('ix_executions_org_status', table_name='executions')
    op.drop_index('ix_executions_runtime_action_id', table_name='executions')
    op.drop_index('ix_executions_organization_id', table_name='executions')
    op.drop_table('executions')
