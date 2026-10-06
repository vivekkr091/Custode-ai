"""add_mcp_tables

Revision ID: 0016_add_mcp_tables
Revises: 0015_add_llm_interactions
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016_add_mcp_tables'
down_revision: Union[str, None] = '0015_add_llm_interactions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create mcp_servers table
    op.create_table(
        'mcp_servers',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('server_type', sa.String(length=50), nullable=False, server_default='REMOTE'),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('transport', sa.String(length=50), nullable=False, server_default='HTTP'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='ACTIVE'),
        sa.Column('trust_level', sa.String(length=30), nullable=False, server_default='UNTRUSTED'),
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='development'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_mcp_servers_org_slug')
    )
    op.create_index('ix_mcp_servers_organization_id', 'mcp_servers', ['organization_id'], unique=False)
    op.create_index('ix_mcp_servers_org_status', 'mcp_servers', ['organization_id', 'status'], unique=False)
    op.create_index('ix_mcp_servers_org_trust', 'mcp_servers', ['organization_id', 'trust_level'], unique=False)
    op.create_index('ix_mcp_servers_org_created_at', 'mcp_servers', ['organization_id', 'created_at'], unique=False)

    # 2. Create mcp_tools table
    op.create_table(
        'mcp_tools',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('mcp_server_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('tool_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('operation_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema', sa.JSON(), nullable=False),
        sa.Column('output_schema', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='DISCOVERED'),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('schema_hash', sa.String(length=64), nullable=False),
        sa.Column('previous_schema_hash', sa.String(length=64), nullable=True),
        sa.Column('schema_changed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mcp_server_id'], ['mcp_servers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['operation_id'], ['tool_operations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mcp_server_id', 'slug', name='uq_mcp_tools_server_slug')
    )
    op.create_index('ix_mcp_tools_organization_id', 'mcp_tools', ['organization_id'], unique=False)
    op.create_index('ix_mcp_tools_mcp_server_id', 'mcp_tools', ['mcp_server_id'], unique=False)
    op.create_index('ix_mcp_tools_org_status', 'mcp_tools', ['organization_id', 'status'], unique=False)
    op.create_index('ix_mcp_tools_org_schema_drift', 'mcp_tools', ['organization_id', 'schema_changed'], unique=False)

    # 3. Alter security_findings table to add mcp_server_id, mcp_tool_id, and make runtime_action_id nullable
    with op.batch_alter_table('security_findings') as batch_op:
        batch_op.alter_column('runtime_action_id', existing_type=sa.Uuid(as_uuid=True), nullable=True)
        batch_op.add_column(sa.Column('mcp_server_id', sa.Uuid(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column('mcp_tool_id', sa.Uuid(as_uuid=True), nullable=True))
        batch_op.create_foreign_key('fk_security_findings_mcp_server', 'mcp_servers', ['mcp_server_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_security_findings_mcp_tool', 'mcp_tools', ['mcp_tool_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index('ix_security_findings_mcp_server_id', ['mcp_server_id'], unique=False)
        batch_op.create_index('ix_security_findings_mcp_tool_id', ['mcp_tool_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('security_findings') as batch_op:
        batch_op.drop_index('ix_security_findings_mcp_tool_id')
        batch_op.drop_index('ix_security_findings_mcp_server_id')
        batch_op.drop_constraint('fk_security_findings_mcp_tool', type_='foreignkey')
        batch_op.drop_constraint('fk_security_findings_mcp_server', type_='foreignkey')
        batch_op.drop_column('mcp_tool_id')
        batch_op.drop_column('mcp_server_id')
        batch_op.alter_column('runtime_action_id', existing_type=sa.Uuid(as_uuid=True), nullable=False)

    op.drop_table('mcp_tools')
    op.drop_table('mcp_servers')
