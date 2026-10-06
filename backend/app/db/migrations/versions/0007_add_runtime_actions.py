"""add_runtime_actions

Revision ID: 0007_add_runtime_actions
Revises: 0006_add_policies_and_policy_versions
Create Date: 2026-09-29 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0007_add_runtime_actions'
down_revision: Union[str, None] = '0006_add_policies_and_policy_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'runtime_actions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('tool_id', sa.Uuid(), nullable=False),
        sa.Column('operation_id', sa.Uuid(), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('environment', sa.String(length=20), server_default='dev', nullable=False),
        sa.Column('resource', sa.String(length=500), nullable=True),
        sa.Column('resource_type', sa.String(length=100), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column(
            'parameters',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column('amount', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['operation_id'], ['tool_operations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_runtime_actions_organization_id', 'runtime_actions', ['organization_id'], unique=False)
    op.create_index('ix_runtime_actions_org_agent', 'runtime_actions', ['organization_id', 'agent_id'], unique=False)
    op.create_index('ix_runtime_actions_org_created_at', 'runtime_actions', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_runtime_actions_request_id', 'runtime_actions', ['request_id'], unique=False)
    op.create_index('ix_runtime_actions_status', 'runtime_actions', ['status'], unique=False)
    op.create_index('ix_runtime_actions_environment', 'runtime_actions', ['environment'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_runtime_actions_environment', table_name='runtime_actions')
    op.drop_index('ix_runtime_actions_status', table_name='runtime_actions')
    op.drop_index('ix_runtime_actions_request_id', table_name='runtime_actions')
    op.drop_index('ix_runtime_actions_org_created_at', table_name='runtime_actions')
    op.drop_index('ix_runtime_actions_org_agent', table_name='runtime_actions')
    op.drop_index('ix_runtime_actions_organization_id', table_name='runtime_actions')
    op.drop_table('runtime_actions')
