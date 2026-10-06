"""add_permissions

Revision ID: 0005_add_permissions
Revises: 0004_add_tools_and_tool_operations
Create Date: 2026-09-29 00:44:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_permissions'
down_revision: Union[str, None] = '0004_add_tools_and_tool_operations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('tool_id', sa.Uuid(), nullable=False),
        sa.Column('operation_id', sa.Uuid(), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False),
        sa.Column('effect', sa.String(length=20), server_default='allow', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['operation_id'], ['tool_operations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'organization_id',
            'agent_id',
            'tool_id',
            'operation_id',
            'environment',
            'effect',
            name='uq_permissions_identity_effect',
        ),
    )
    op.create_index(
        'ix_permissions_eval_lookup',
        'permissions',
        ['organization_id', 'agent_id', 'tool_id', 'operation_id', 'environment', 'status'],
        unique=False,
    )
    op.create_index('ix_permissions_organization_id', 'permissions', ['organization_id'], unique=False)
    op.create_index('ix_permissions_agent_id', 'permissions', ['agent_id'], unique=False)
    op.create_index('ix_permissions_tool_id', 'permissions', ['tool_id'], unique=False)
    op.create_index('ix_permissions_operation_id', 'permissions', ['operation_id'], unique=False)
    op.create_index('ix_permissions_environment', 'permissions', ['environment'], unique=False)
    op.create_index('ix_permissions_status', 'permissions', ['status'], unique=False)
    op.create_index('ix_permissions_effect', 'permissions', ['effect'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_permissions_effect', table_name='permissions')
    op.drop_index('ix_permissions_status', table_name='permissions')
    op.drop_index('ix_permissions_environment', table_name='permissions')
    op.drop_index('ix_permissions_operation_id', table_name='permissions')
    op.drop_index('ix_permissions_tool_id', table_name='permissions')
    op.drop_index('ix_permissions_agent_id', table_name='permissions')
    op.drop_index('ix_permissions_organization_id', table_name='permissions')
    op.drop_index('ix_permissions_eval_lookup', table_name='permissions')
    op.drop_table('permissions')
