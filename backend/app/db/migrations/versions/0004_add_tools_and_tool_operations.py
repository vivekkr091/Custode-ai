"""add_tools_and_tool_operations

Revision ID: 0004_add_tools_and_tool_operations
Revises: 0003_add_agent_credentials
Create Date: 2026-09-29 00:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_tools_and_tool_operations'
down_revision: Union[str, None] = '0003_add_agent_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tools table
    op.create_table(
        'tools',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('tool_type', sa.String(length=50), server_default='api', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('environment', sa.String(length=50), server_default='development', nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_tools_org_slug'),
    )
    op.create_index('ix_tools_organization_id', 'tools', ['organization_id'], unique=False)
    op.create_index('ix_tools_status', 'tools', ['status'], unique=False)
    op.create_index('ix_tools_environment', 'tools', ['environment'], unique=False)

    # 2. Tool Operations table
    op.create_table(
        'tool_operations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tool_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('operation_type', sa.String(length=50), server_default='read', nullable=False),
        sa.Column('risk_level', sa.String(length=50), server_default='medium', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tool_id', 'slug', name='uq_tool_operations_tool_slug'),
    )
    op.create_index('ix_tool_operations_tool_id', 'tool_operations', ['tool_id'], unique=False)
    op.create_index('ix_tool_operations_status', 'tool_operations', ['status'], unique=False)
    op.create_index('ix_tool_operations_operation_type', 'tool_operations', ['operation_type'], unique=False)
    op.create_index('ix_tool_operations_risk_level', 'tool_operations', ['risk_level'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tool_operations_risk_level', table_name='tool_operations')
    op.drop_index('ix_tool_operations_operation_type', table_name='tool_operations')
    op.drop_index('ix_tool_operations_status', table_name='tool_operations')
    op.drop_index('ix_tool_operations_tool_id', table_name='tool_operations')
    op.drop_table('tool_operations')

    op.drop_index('ix_tools_environment', table_name='tools')
    op.drop_index('ix_tools_status', table_name='tools')
    op.drop_index('ix_tools_organization_id', table_name='tools')
    op.drop_table('tools')
