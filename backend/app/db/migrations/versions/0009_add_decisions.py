"""add_decisions

Revision ID: 0009_add_decisions
Revises: 0008_add_risk_assessments
Create Date: 2026-09-29 01:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0009_add_decisions'
down_revision: Union[str, None] = '0008_add_risk_assessments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'decisions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(), nullable=False),
        sa.Column('decision', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('risk_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('permission_effect', sa.String(length=20), nullable=True),
        sa.Column('policy_effect', sa.String(length=30), nullable=True),
        sa.Column('policy_id', sa.Uuid(), nullable=True),
        sa.Column('policy_version_id', sa.Uuid(), nullable=True),
        sa.Column(
            'factors',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column(
            'evaluation_trace',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column('engine_version', sa.String(length=20), server_default='1.0.0', nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_decisions_organization_id', 'decisions', ['organization_id'], unique=False)
    op.create_index('ix_decisions_runtime_action_id', 'decisions', ['runtime_action_id'], unique=False)
    op.create_index('ix_decisions_org_decision', 'decisions', ['organization_id', 'decision'], unique=False)
    op.create_index('ix_decisions_org_created_at', 'decisions', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_decisions_org_created_at', table_name='decisions')
    op.drop_index('ix_decisions_org_decision', table_name='decisions')
    op.drop_index('ix_decisions_runtime_action_id', table_name='decisions')
    op.drop_index('ix_decisions_organization_id', table_name='decisions')
    op.drop_table('decisions')
