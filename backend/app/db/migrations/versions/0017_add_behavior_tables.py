"""add_behavior_tables

Revision ID: 0017_add_behavior_tables
Revises: 0016_add_mcp_tables
Create Date: 2026-10-01 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0017_add_behavior_tables'
down_revision: Union[str, None] = '0016_add_mcp_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agent_behavior_baselines table
    op.create_table(
        'agent_behavior_baselines',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('agent_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='production'),
        sa.Column('state', sa.String(length=50), nullable=False, server_default='COLD_START'),
        sa.Column('observation_window_seconds', sa.Integer(), nullable=False, server_default='86400'),
        sa.Column('action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocked_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approval_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tool_counts', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('operation_counts', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('resource_counts', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('sensitive_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('destructive_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transfer_action_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('amount_variance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_actions_per_hour', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('peak_actions_per_hour', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('operational_hours_start', sa.Integer(), nullable=False, server_default='8'),
        sa.Column('operational_hours_end', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('baseline_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'agent_id', 'environment', name='uq_agent_env_baseline'),
    )
    op.create_index('ix_agent_behavior_baselines_organization_id', 'agent_behavior_baselines', ['organization_id'], unique=False)
    op.create_index('ix_agent_behavior_baselines_agent_id', 'agent_behavior_baselines', ['agent_id'], unique=False)
    op.create_index('ix_agent_behavior_baselines_environment', 'agent_behavior_baselines', ['environment'], unique=False)
    op.create_index('ix_agent_behavior_baselines_state', 'agent_behavior_baselines', ['state'], unique=False)
    op.create_index('ix_agent_behavior_baselines_org_state', 'agent_behavior_baselines', ['organization_id', 'state'], unique=False)

    # 2. Create behavioral_anomalies table
    op.create_table(
        'behavioral_anomalies',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('agent_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('anomaly_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='LOW'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('feature', sa.String(length=100), nullable=False),
        sa.Column('baseline_value', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('observed_value', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('deviation', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('environment', sa.String(length=50), nullable=False, server_default='production'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='OPEN'),
        sa.Column('resolved_by', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_behavioral_anomalies_organization_id', 'behavioral_anomalies', ['organization_id'], unique=False)
    op.create_index('ix_behavioral_anomalies_agent_id', 'behavioral_anomalies', ['agent_id'], unique=False)
    op.create_index('ix_behavioral_anomalies_runtime_action_id', 'behavioral_anomalies', ['runtime_action_id'], unique=False)
    op.create_index('ix_behavioral_anomalies_anomaly_type', 'behavioral_anomalies', ['anomaly_type'], unique=False)
    op.create_index('ix_behavioral_anomalies_severity', 'behavioral_anomalies', ['severity'], unique=False)
    op.create_index('ix_behavioral_anomalies_feature', 'behavioral_anomalies', ['feature'], unique=False)
    op.create_index('ix_behavioral_anomalies_status', 'behavioral_anomalies', ['status'], unique=False)
    op.create_index('ix_behavioral_anomalies_environment', 'behavioral_anomalies', ['environment'], unique=False)
    op.create_index('ix_behavioral_anomalies_org_agent', 'behavioral_anomalies', ['organization_id', 'agent_id'], unique=False)
    op.create_index('ix_behavioral_anomalies_org_status', 'behavioral_anomalies', ['organization_id', 'status'], unique=False)
    op.create_index('ix_behavioral_anomalies_created_at', 'behavioral_anomalies', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('behavioral_anomalies')
    op.drop_table('agent_behavior_baselines')
