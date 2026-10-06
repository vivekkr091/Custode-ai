"""add_policies_and_policy_versions

Revision ID: 0006_add_policies_and_policy_versions
Revises: 0005_add_permissions
Create Date: 2026-09-29 01:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0006_add_policies_and_policy_versions'
down_revision: Union[str, None] = '0005_add_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Policies table
    op.create_table(
        'policies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('enforcement_mode', sa.String(length=20), server_default='enforce', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_policies_org_slug'),
    )
    op.create_index('ix_policies_organization_id', 'policies', ['organization_id'], unique=False)
    op.create_index('ix_policies_status', 'policies', ['status'], unique=False)
    op.create_index('ix_policies_slug', 'policies', ['slug'], unique=False)

    # 2. Policy Versions table
    op.create_table(
        'policy_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('policy_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column(
            'rules',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_id', 'version', name='uq_policy_versions_policy_version'),
    )
    op.create_index('ix_policy_versions_policy_id', 'policy_versions', ['policy_id'], unique=False)
    op.create_index('ix_policy_versions_status', 'policy_versions', ['status'], unique=False)
    op.create_index('ix_policy_versions_version', 'policy_versions', ['version'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_policy_versions_version', table_name='policy_versions')
    op.drop_index('ix_policy_versions_status', table_name='policy_versions')
    op.drop_index('ix_policy_versions_policy_id', table_name='policy_versions')
    op.drop_table('policy_versions')

    op.drop_index('ix_policies_slug', table_name='policies')
    op.drop_index('ix_policies_status', table_name='policies')
    op.drop_index('ix_policies_organization_id', table_name='policies')
    op.drop_table('policies')
