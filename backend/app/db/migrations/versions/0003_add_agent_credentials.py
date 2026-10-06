"""add_agent_credentials

Revision ID: 0003_add_agent_credentials
Revises: 0002_add_agents
Create Date: 2026-09-29 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_agent_credentials'
down_revision: Union[str, None] = '0002_add_agents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_credentials',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('credential_prefix', sa.String(length=64), nullable=False),
        sa.Column('credential_hash', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_prefix', name='uq_agent_credentials_prefix'),
    )
    op.create_index('ix_agent_credentials_agent_id', 'agent_credentials', ['agent_id'], unique=False)
    op.create_index('ix_agent_credentials_prefix', 'agent_credentials', ['credential_prefix'], unique=False)
    op.create_index('ix_agent_credentials_status', 'agent_credentials', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_agent_credentials_status', table_name='agent_credentials')
    op.drop_index('ix_agent_credentials_prefix', table_name='agent_credentials')
    op.drop_index('ix_agent_credentials_agent_id', table_name='agent_credentials')
    op.drop_table('agent_credentials')
