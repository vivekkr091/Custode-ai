"""add_approvals

Revision ID: 0010_add_approvals
Revises: 0009_add_decisions
Create Date: 2026-09-29 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '0010_add_approvals'
down_revision: Union[str, None] = '0009_add_decisions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('runtime_action_id', sa.Uuid(), nullable=False),
        sa.Column('decision_id', sa.Uuid(), nullable=False),
        sa.Column('requested_by_agent_id', sa.Uuid(), nullable=False),
        sa.Column('reviewer_user_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'decision_snapshot',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column(
            'approval_context',
            sa.JSON().with_variant(JSONB, 'postgresql'),
            nullable=False,
        ),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['runtime_action_id'], ['runtime_actions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approval_requests_organization_id', 'approval_requests', ['organization_id'], unique=False)
    op.create_index('ix_approval_requests_runtime_action_id', 'approval_requests', ['runtime_action_id'], unique=False)
    op.create_index('ix_approval_requests_org_status', 'approval_requests', ['organization_id', 'status'], unique=False)
    op.create_index('ix_approval_requests_reviewer_user_id', 'approval_requests', ['reviewer_user_id'], unique=False)
    op.create_index('ix_approval_requests_org_created_at', 'approval_requests', ['organization_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_approval_requests_org_created_at', table_name='approval_requests')
    op.drop_index('ix_approval_requests_reviewer_user_id', table_name='approval_requests')
    op.drop_index('ix_approval_requests_org_status', table_name='approval_requests')
    op.drop_index('ix_approval_requests_runtime_action_id', table_name='approval_requests')
    op.drop_index('ix_approval_requests_organization_id', table_name='approval_requests')
    op.drop_table('approval_requests')
