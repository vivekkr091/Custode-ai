"""add_security_audit_events

Revision ID: 0013_add_security_audit_events
Revises: 0012_add_auth_and_audit
Create Date: 2026-09-29 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013_add_security_audit_events'
down_revision: Union[str, None] = '0012_add_auth_and_audit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new audit taxonomy and actor tracking columns
    op.add_column(
        'audit_events',
        sa.Column('actor_type', sa.String(length=50), nullable=False, server_default='USER')
    )
    op.add_column(
        'audit_events',
        sa.Column('actor_id', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'audit_events',
        sa.Column('actor_display', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'audit_events',
        sa.Column('event_type', sa.String(length=100), nullable=False, server_default='CUSTOM')
    )
    op.add_column(
        'audit_events',
        sa.Column('resource_type', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'audit_events',
        sa.Column('resource_id', sa.String(length=255), nullable=True)
    )

    # Create search and correlation indexes
    op.create_index('ix_audit_events_actor_type', 'audit_events', ['actor_type'], unique=False)
    op.create_index('ix_audit_events_actor_id', 'audit_events', ['actor_id'], unique=False)
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'], unique=False)
    op.create_index('ix_audit_events_resource_type', 'audit_events', ['resource_type'], unique=False)
    op.create_index('ix_audit_events_resource_id', 'audit_events', ['resource_id'], unique=False)
    op.create_index('ix_audit_events_request_id', 'audit_events', ['request_id'], unique=False)
    op.create_index('ix_audit_events_outcome', 'audit_events', ['outcome'], unique=False)
    op.create_index('ix_audit_events_org_event_type', 'audit_events', ['organization_id', 'event_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_events_org_event_type', table_name='audit_events')
    op.drop_index('ix_audit_events_outcome', table_name='audit_events')
    op.drop_index('ix_audit_events_request_id', table_name='audit_events')
    op.drop_index('ix_audit_events_resource_id', table_name='audit_events')
    op.drop_index('ix_audit_events_resource_type', table_name='audit_events')
    op.drop_index('ix_audit_events_event_type', table_name='audit_events')
    op.drop_index('ix_audit_events_actor_id', table_name='audit_events')
    op.drop_index('ix_audit_events_actor_type', table_name='audit_events')

    op.drop_column('audit_events', 'resource_id')
    op.drop_column('audit_events', 'resource_type')
    op.drop_column('audit_events', 'event_type')
    op.drop_column('audit_events', 'actor_display')
    op.drop_column('audit_events', 'actor_id')
    op.drop_column('audit_events', 'actor_type')
