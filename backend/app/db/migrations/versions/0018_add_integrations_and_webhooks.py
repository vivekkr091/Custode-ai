"""add_integrations_and_webhooks

Revision ID: 0018_add_integrations_and_webhooks
Revises: 0017_add_behavior_tables
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018_add_integrations_and_webhooks'
down_revision: Union[str, None] = '0017_add_behavior_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create integrations table
    op.create_table(
        'integrations',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='webhook'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('secret_prefix', sa.String(length=30), nullable=False),
        sa.Column('secret_hash', sa.String(length=255), nullable=False),
        sa.Column('encrypted_secret', sa.Text(), nullable=False),
        sa.Column('subscribed_events', sa.JSON(), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('last_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_integrations_organization_id', 'integrations', ['organization_id'], unique=False)
    op.create_index('ix_integrations_provider', 'integrations', ['provider'], unique=False)
    op.create_index('ix_integrations_status', 'integrations', ['status'], unique=False)
    op.create_index('ix_integrations_secret_prefix', 'integrations', ['secret_prefix'], unique=False)
    op.create_index('ix_integrations_org_status', 'integrations', ['organization_id', 'status'], unique=False)
    op.create_index('ix_integrations_org_provider', 'integrations', ['organization_id', 'provider'], unique=False)

    # 2. Create webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('integration_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('event_id', sa.String(length=100), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('delivery_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('sanitized_response_summary', sa.String(length=500), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_deliveries_organization_id', 'webhook_deliveries', ['organization_id'], unique=False)
    op.create_index('ix_webhook_deliveries_integration_id', 'webhook_deliveries', ['integration_id'], unique=False)
    op.create_index('ix_webhook_deliveries_event_id', 'webhook_deliveries', ['event_id'], unique=False)
    op.create_index('ix_webhook_deliveries_event_type', 'webhook_deliveries', ['event_type'], unique=False)
    op.create_index('ix_webhook_deliveries_request_id', 'webhook_deliveries', ['request_id'], unique=False)
    op.create_index('ix_webhook_deliveries_delivery_status', 'webhook_deliveries', ['delivery_status'], unique=False)
    op.create_index('ix_webhook_deliveries_next_retry_at', 'webhook_deliveries', ['next_retry_at'], unique=False)
    op.create_index('ix_webhook_deliveries_org_status', 'webhook_deliveries', ['organization_id', 'delivery_status'], unique=False)
    op.create_index('ix_webhook_deliveries_org_created_at', 'webhook_deliveries', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_webhook_deliveries_integration_status', 'webhook_deliveries', ['integration_id', 'delivery_status'], unique=False)

    # 3. Create webhook_attempts table
    op.create_table(
        'webhook_attempts',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('delivery_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('sanitized_error', sa.String(length=500), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['delivery_id'], ['webhook_deliveries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_attempts_delivery_id', 'webhook_attempts', ['delivery_id'], unique=False)
    op.create_index('ix_webhook_attempts_delivery_attempt', 'webhook_attempts', ['delivery_id', 'attempt_number'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_webhook_attempts_delivery_attempt', table_name='webhook_attempts')
    op.drop_index('ix_webhook_attempts_delivery_id', table_name='webhook_attempts')
    op.drop_table('webhook_attempts')

    op.drop_index('ix_webhook_deliveries_integration_status', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_org_created_at', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_org_status', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_next_retry_at', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_delivery_status', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_request_id', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_event_type', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_event_id', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_integration_id', table_name='webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_organization_id', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')

    op.drop_index('ix_integrations_org_provider', table_name='integrations')
    op.drop_index('ix_integrations_org_status', table_name='integrations')
    op.drop_index('ix_integrations_secret_prefix', table_name='integrations')
    op.drop_index('ix_integrations_status', table_name='integrations')
    op.drop_index('ix_integrations_provider', table_name='integrations')
    op.drop_index('ix_integrations_organization_id', table_name='integrations')
    op.drop_table('integrations')
