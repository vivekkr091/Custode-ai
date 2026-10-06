"""add_llm_interactions

Revision ID: 0015_add_llm_interactions
Revises: 0014_add_security_findings_and_scans
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0015_add_llm_interactions'
down_revision: Union[str, None] = '0014_add_security_findings_and_scans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create llm_interactions table
    op.create_table(
        'llm_interactions',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('agent_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(as_uuid=True), nullable=True),
        sa.Column('request_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=150), nullable=False),
        sa.Column('environment', sa.String(length=20), nullable=False, server_default='dev'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('input_scan_status', sa.String(length=50), nullable=False, server_default='skipped'),
        sa.Column('output_scan_status', sa.String(length=50), nullable=False, server_default='skipped'),
        sa.Column('decision', sa.String(length=30), nullable=False, server_default='allow'),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='low'),
        sa.Column('latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_hash', sa.String(length=64), nullable=False),
        sa.Column('output_hash', sa.String(length=64), nullable=True),
        sa.Column('sanitized_prompt_preview', sa.Text(), nullable=True),
        sa.Column('sanitized_output_preview', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_interactions_organization_id', 'llm_interactions', ['organization_id'], unique=False)
    op.create_index('ix_llm_interactions_agent_id', 'llm_interactions', ['agent_id'], unique=False)
    op.create_index('ix_llm_interactions_runtime_action_id', 'llm_interactions', ['runtime_action_id'], unique=False)
    op.create_index('ix_llm_interactions_request_id', 'llm_interactions', ['request_id'], unique=False)
    op.create_index('ix_llm_interactions_provider', 'llm_interactions', ['provider'], unique=False)
    op.create_index('ix_llm_interactions_model', 'llm_interactions', ['model'], unique=False)
    op.create_index('ix_llm_interactions_environment', 'llm_interactions', ['environment'], unique=False)
    op.create_index('ix_llm_interactions_status', 'llm_interactions', ['status'], unique=False)
    op.create_index('ix_llm_interactions_decision', 'llm_interactions', ['decision'], unique=False)
    op.create_index('ix_llm_interactions_input_hash', 'llm_interactions', ['input_hash'], unique=False)
    op.create_index('ix_llm_interactions_org_created_at', 'llm_interactions', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_llm_interactions_org_provider', 'llm_interactions', ['organization_id', 'provider'], unique=False)
    op.create_index('ix_llm_interactions_org_status', 'llm_interactions', ['organization_id', 'status'], unique=False)
    op.create_index('ix_llm_interactions_org_model', 'llm_interactions', ['organization_id', 'model'], unique=False)

    # 2. Add scan_direction and interaction_id to security_findings using batch mode
    with op.batch_alter_table('security_findings') as batch_op:
        batch_op.add_column(sa.Column('scan_direction', sa.String(length=20), nullable=False, server_default='INPUT'))
        batch_op.add_column(sa.Column('interaction_id', sa.Uuid(as_uuid=True), nullable=True))
        batch_op.create_foreign_key(
            'fk_security_findings_interaction_id',
            'llm_interactions',
            ['interaction_id'],
            ['id'],
            ondelete='CASCADE'
        )
        batch_op.create_index('ix_security_findings_scan_direction', ['scan_direction'], unique=False)
        batch_op.create_index('ix_security_findings_interaction_id', ['interaction_id'], unique=False)
        batch_op.create_index('ix_security_findings_org_direction', ['organization_id', 'scan_direction'], unique=False)


def downgrade() -> None:
    # 1. Remove columns and constraints from security_findings using batch mode
    with op.batch_alter_table('security_findings') as batch_op:
        batch_op.drop_index('ix_security_findings_org_direction')
        batch_op.drop_index('ix_security_findings_interaction_id')
        batch_op.drop_index('ix_security_findings_scan_direction')
        batch_op.drop_constraint('fk_security_findings_interaction_id', type_='foreignkey')
        batch_op.drop_column('interaction_id')
        batch_op.drop_column('scan_direction')

    # 2. Drop llm_interactions indexes and table
    op.drop_index('ix_llm_interactions_org_model', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_org_status', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_org_provider', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_org_created_at', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_input_hash', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_decision', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_status', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_environment', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_model', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_provider', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_request_id', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_runtime_action_id', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_agent_id', table_name='llm_interactions')
    op.drop_index('ix_llm_interactions_organization_id', table_name='llm_interactions')
    op.drop_table('llm_interactions')
