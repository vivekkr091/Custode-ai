"""add_risk_assessments

Revision ID: 0008_add_risk_assessments
Revises: 0007_add_runtime_actions
Create Date: 2026-09-29 01:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0008_add_risk_assessments'
down_revision: Union[str, None] = '0007_add_runtime_actions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'risk_assessments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('risk_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            'factors',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column(
            'triggered_rules',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('engine_version', sa.String(length=20), server_default='1.0.0', nullable=False),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_risk_assessments_organization_id', 'risk_assessments', ['organization_id'], unique=False)
    op.create_index('ix_risk_assessments_runtime_action_id', 'risk_assessments', ['runtime_action_id'], unique=False)
    op.create_index('ix_risk_assessments_org_risk_level', 'risk_assessments', ['organization_id', 'risk_level'], unique=False)
    op.create_index('ix_risk_assessments_org_created_at', 'risk_assessments', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_risk_assessments_org_created_at', table_name='risk_assessments')
    op.drop_index('ix_risk_assessments_org_risk_level', table_name='risk_assessments')
    op.drop_index('ix_risk_assessments_runtime_action_id', table_name='risk_assessments')
    op.drop_index('ix_risk_assessments_organization_id', table_name='risk_assessments')
    op.drop_table('risk_assessments')
