"""add_security_findings_and_scans

Revision ID: 0014_add_security_findings_and_scans
Revises: 0013_add_security_audit_events
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0014_add_security_findings_and_scans'
down_revision: Union[str, None] = '0013_add_security_audit_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create security_scans table
    op.create_table(
        'security_scans',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('scanner_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('findings_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('high_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('medium_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('highest_severity', sa.String(length=20), nullable=False, server_default='NONE'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='completed'),
        sa.Column('scanners_run', sa.JSON(), nullable=False),
        sa.Column('execution_time_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_security_scans_organization_id', 'security_scans', ['organization_id'], unique=False)
    op.create_index('ix_security_scans_runtime_action_id', 'security_scans', ['runtime_action_id'], unique=False)
    op.create_index('ix_security_scans_highest_severity', 'security_scans', ['highest_severity'], unique=False)
    op.create_index('ix_security_scans_status', 'security_scans', ['status'], unique=False)
    op.create_index('ix_security_scans_org_created_at', 'security_scans', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_security_scans_org_action', 'security_scans', ['organization_id', 'runtime_action_id'], unique=False)

    # 2. Create security_findings table
    op.create_table(
        'security_findings',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('scan_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('scanner', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('remediation', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='sentinel'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scan_id'], ['security_scans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_security_findings_organization_id', 'security_findings', ['organization_id'], unique=False)
    op.create_index('ix_security_findings_runtime_action_id', 'security_findings', ['runtime_action_id'], unique=False)
    op.create_index('ix_security_findings_scan_id', 'security_findings', ['scan_id'], unique=False)
    op.create_index('ix_security_findings_scanner', 'security_findings', ['scanner'], unique=False)
    op.create_index('ix_security_findings_category', 'security_findings', ['category'], unique=False)
    op.create_index('ix_security_findings_severity', 'security_findings', ['severity'], unique=False)
    op.create_index('ix_security_findings_org_severity', 'security_findings', ['organization_id', 'severity'], unique=False)
    op.create_index('ix_security_findings_org_category', 'security_findings', ['organization_id', 'category'], unique=False)
    op.create_index('ix_security_findings_org_action', 'security_findings', ['organization_id', 'runtime_action_id'], unique=False)
    op.create_index('ix_security_findings_org_created_at', 'security_findings', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop security_findings indexes and table
    op.drop_index('ix_security_findings_org_created_at', table_name='security_findings')
    op.drop_index('ix_security_findings_org_action', table_name='security_findings')
    op.drop_index('ix_security_findings_org_category', table_name='security_findings')
    op.drop_index('ix_security_findings_org_severity', table_name='security_findings')
    op.drop_index('ix_security_findings_severity', table_name='security_findings')
    op.drop_index('ix_security_findings_category', table_name='security_findings')
    op.drop_index('ix_security_findings_scanner', table_name='security_findings')
    op.drop_index('ix_security_findings_scan_id', table_name='security_findings')
    op.drop_index('ix_security_findings_runtime_action_id', table_name='security_findings')
    op.drop_index('ix_security_findings_organization_id', table_name='security_findings')
    op.drop_table('security_findings')

    # Drop security_scans indexes and table
    op.drop_index('ix_security_scans_org_action', table_name='security_scans')
    op.drop_index('ix_security_scans_org_created_at', table_name='security_scans')
    op.drop_index('ix_security_scans_status', table_name='security_scans')
    op.drop_index('ix_security_scans_highest_severity', table_name='security_scans')
    op.drop_index('ix_security_scans_runtime_action_id', table_name='security_scans')
    op.drop_index('ix_security_scans_organization_id', table_name='security_scans')
    op.drop_table('security_scans')
