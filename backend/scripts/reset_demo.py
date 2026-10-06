#!/usr/bin/env python3
"""Safe Demo Reset Script for CUSTODE v0.1.0-rc1.

Purges synthetic demonstration data associated strictly with organization
'Acme Travel AI' (slug: acme-travel-ai).

CRITICAL SAFETY SAFEGUARDS:
1. Refuses to run if ENVIRONMENT == 'production' or 'prod'.
2. Refuses to run if DATABASE_URL appears to target a production host.
3. Never affects the default organization ('custode-cyber-defense') or real customer tenants.
4. Cascades deletions deterministically respecting foreign key constraints.
"""

import argparse
import asyncio
import os
import sys
import uuid

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.agent import Agent
from app.db.models.agent_behavior_baseline import AgentBehaviorBaseline
from app.db.models.agent_credential import AgentCredential
from app.db.models.approval import ApprovalRequest
from app.db.models.audit_event import AuditEvent
from app.db.models.behavioral_anomaly import BehavioralAnomaly
from app.db.models.decision import Decision
from app.db.models.execution import Execution
from app.db.models.integration import Integration
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.permission import Permission
from app.db.models.policy import Policy
from app.db.models.policy_version import PolicyVersion
from app.db.models.risk_assessment import RiskAssessment
from app.db.models.runtime_action import RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.security_scan import SecurityScan
from app.db.models.tool import Tool
from app.db.models.tool_operation import ToolOperation
from app.db.models.webhook_delivery import WebhookDelivery
from app.db.session import close_engine, get_session_factory


DEMO_ORG_SLUG = "acme-travel-ai"


def assert_safe_environment() -> None:
    """Verify that current environment is not production."""
    settings = get_settings()

    env_name = getattr(settings, "ENVIRONMENT", "development").lower()
    if env_name in {"production", "prod"}:
        raise RuntimeError(
            f"SAFETY GUARD TRIGGERED: Refusing to reset demo data in environment '{env_name}'."
        )

    db_url = settings.DATABASE_URL.lower()
    prod_keywords = ["prod", "production", "rds.amazonaws.com", "cloudsql", "azure.com"]
    # Allow local sqlite/postgres
    if any(k in db_url for k in prod_keywords) and "test" not in db_url and "local" not in db_url:
        raise RuntimeError(
            f"SAFETY GUARD TRIGGERED: DATABASE_URL appears to target a production database: {settings.DATABASE_URL}"
        )


async def reset_demo_environment() -> bool:
    """Safely purge all demonstration data for Acme Travel AI."""
    assert_safe_environment()
    session_factory = get_session_factory()

    async with session_factory() as session:
        print(f"[custode-reset] Locating demo organization with slug '{DEMO_ORG_SLUG}'...")
        org_res = await session.execute(
            select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
        )
        org = org_res.scalar_one_or_none()
        if org is None:
            print(f"[custode-reset] No demo organization '{DEMO_ORG_SLUG}' found. Environment is already clean.")
            return True

        org_id = org.id
        print(f"[custode-reset] Found demo organization '{org.name}' ({org_id}). Beginning safe purge...")

        # 1. Fetch related tool IDs for child operation cascading
        tools_res = await session.execute(select(Tool.id).where(Tool.organization_id == org_id))
        tool_ids = list(tools_res.scalars().all())

        # 2. Fetch related policy IDs for version cascading
        policies_res = await session.execute(select(Policy.id).where(Policy.organization_id == org_id))
        policy_ids = list(policies_res.scalars().all())

        # 3. Cascading delete in reverse dependency order
        # Executions & Approvals
        await session.execute(delete(Execution).where(Execution.organization_id == org_id))
        await session.execute(delete(ApprovalRequest).where(ApprovalRequest.organization_id == org_id))

        # Decisions & Risk Assessments
        await session.execute(delete(Decision).where(Decision.organization_id == org_id))
        await session.execute(delete(RiskAssessment).where(RiskAssessment.organization_id == org_id))

        # Security Findings & Scans
        await session.execute(delete(SecurityFinding).where(SecurityFinding.organization_id == org_id))
        await session.execute(delete(SecurityScan).where(SecurityScan.organization_id == org_id))

        # Behavioral Anomalies & Baselines
        await session.execute(delete(BehavioralAnomaly).where(BehavioralAnomaly.organization_id == org_id))
        await session.execute(delete(AgentBehaviorBaseline).where(AgentBehaviorBaseline.organization_id == org_id))

        # Webhooks & Integrations
        await session.execute(delete(WebhookDelivery).where(WebhookDelivery.organization_id == org_id))
        await session.execute(delete(Integration).where(Integration.organization_id == org_id))

        # Runtime Actions
        await session.execute(delete(RuntimeAction).where(RuntimeAction.organization_id == org_id))

        # Permissions
        await session.execute(delete(Permission).where(Permission.organization_id == org_id))

        # Policies & Versions
        if policy_ids:
            await session.execute(delete(PolicyVersion).where(PolicyVersion.policy_id.in_(policy_ids)))
        await session.execute(delete(Policy).where(Policy.organization_id == org_id))

        # Tool Operations & Tools
        if tool_ids:
            await session.execute(delete(ToolOperation).where(ToolOperation.tool_id.in_(tool_ids)))
        await session.execute(delete(Tool).where(Tool.organization_id == org_id))

        # Agent Credentials & Agents
        agents_res = await session.execute(select(Agent.id).where(Agent.organization_id == org_id))
        agent_ids = list(agents_res.scalars().all())
        if agent_ids:
            await session.execute(delete(AgentCredential).where(AgentCredential.agent_id.in_(agent_ids)))
        await session.execute(delete(Agent).where(Agent.organization_id == org_id))

        # Audit events scoped to org
        await session.execute(delete(AuditEvent).where(AuditEvent.organization_id == org_id))

        # Memberships for org
        await session.execute(delete(Membership).where(Membership.organization_id == org_id))

        # Finally, the demo Organization itself
        await session.execute(delete(Organization).where(Organization.id == org_id))

        await session.commit()
        print(f"[custode-reset] Successfully purged demo organization '{DEMO_ORG_SLUG}' and all associated entities.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Safely reset CUSTODE synthetic demonstration data.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm reset without interactive prompt.",
    )
    args = parser.parse_args()

    if not args.yes:
        confirm = input(f"Are you sure you want to purge synthetic demo data for '{DEMO_ORG_SLUG}'? [y/N]: ")
        if confirm.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            sys.exit(0)

    try:
        asyncio.run(reset_demo_environment())
    finally:
        asyncio.run(close_engine())


if __name__ == "__main__":
    main()
