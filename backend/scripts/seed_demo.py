#!/usr/bin/env python3
"""Synthetic Demo Seeder for CUSTODE v0.1.0-rc1 Showcase.

Builds an idempotent, safe demonstration environment:
- Organization: Acme Travel AI (slug: acme-travel-ai)
- Agent: Travel Assistant Agent
- Tool: Booking Management Tool (slug: booking_tool)
- Operations:
  * search_available_rooms (read, low risk) -> Scenario A (Allowed)
  * cancel_booking (write, medium risk)     -> Scenario B (Blocked / Denied)
  * create_booking (write, high risk)       -> Scenario C (Human Approval Required)
- High-Value Booking Guardrail Policy (amount > $500 -> require_approval)
- Executes Scenario A (SUCCEEDED) and Scenario B (BLOCKED)
- Leaves Scenario C in PENDING approval for interactive UI demonstration (or completes if --approve-c)
"""

import argparse
import asyncio
import os
import sys
import uuid
from typing import Optional

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.agent import Agent, AgentEnvironment, AgentStatus, AgentType
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.decision import Decision
from app.db.models.execution import Execution
from app.db.models.membership import Membership, MembershipRole, MembershipStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.permission import Permission, PermissionEffect, PermissionStatus
from app.db.models.policy import EnforcementMode, Policy, PolicyStatus
from app.db.models.policy_version import PolicyVersion, PolicyVersionStatus
from app.db.models.runtime_action import ActionEnvironment, ActionStatus, RuntimeAction
from app.db.models.tool import Tool, ToolEnvironment, ToolStatus, ToolType
from app.db.models.tool_operation import OperationRiskLevel, OperationStatus, OperationType, ToolOperation
from app.db.models.user import User
from app.db.session import close_engine, get_session_factory
from app.schemas.approval import ApprovalApproveRequest, ApprovalCreate
from app.schemas.permission import PermissionCreate
from app.schemas.policy import PolicyCreate, PolicyRule, PolicyRuleCondition, PolicyVersionCreate
from app.schemas.runtime_action import RuntimeActionCreate
from app.schemas.tool import ToolCreate
from app.schemas.tool_operation import ToolOperationCreate
from app.services.approval import approve_request, create_approval_request
from app.services.decision import decide_runtime_action
from app.services.execution import execute_runtime_action
from app.services.permission import create_permission
from app.services.policy import create_policy, create_policy_version, publish_policy_version
from app.services.runtime_action import create_runtime_action
from app.services.tool import create_tool
from app.services.tool_operation import create_operation
from app.services.user_auth import bootstrap_development_environment


async def seed_demo_environment(approve_scenario_c: bool = False) -> dict:
    """Idempotently seed the Acme Travel AI demonstration scenario."""
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        print("[custode-demo] Initializing demo bootstrap...")

        # 1. Ensure dev users exist
        await bootstrap_development_environment(session)
        await session.commit()

        # 2. Setup Acme Travel AI organization
        org_slug = "acme-travel-ai"
        org_res = await session.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        org = org_res.scalar_one_or_none()
        if org is None:
            org = Organization(
                name="Acme Travel AI",
                slug=org_slug,
                status=OrganizationStatus.active.value,
            )
            session.add(org)
            await session.flush()
            print(f"[custode-demo] Created organization: {org.name} (ID: {org.id})")
        else:
            print(f"[custode-demo] Found existing organization: {org.name} (ID: {org.id})")

        # 3. Associate development users with Acme Travel AI
        admin_user_res = await session.execute(
            select(User).where(User.email == "security.admin@custode.io")
        )
        admin_user = admin_user_res.scalar_one_or_none()

        analyst_user_res = await session.execute(
            select(User).where(User.email == "analyst@custode.io")
        )
        analyst_user = analyst_user_res.scalar_one_or_none()

        auditor_user_res = await session.execute(
            select(User).where(User.email == "auditor@custode.io")
        )
        auditor_user = auditor_user_res.scalar_one_or_none()

        user_roles = [
            (admin_user, MembershipRole.organization_admin.value),
            (analyst_user, MembershipRole.security_analyst.value),
            (auditor_user, MembershipRole.viewer.value),
        ]

        for user_obj, role_val in user_roles:
            if user_obj:
                mem_res = await session.execute(
                    select(Membership).where(
                        Membership.organization_id == org.id,
                        Membership.user_id == user_obj.id,
                    )
                )
                if mem_res.scalar_one_or_none() is None:
                    mem = Membership(
                        organization_id=org.id,
                        user_id=user_obj.id,
                        role=role_val,
                        status=MembershipStatus.active.value,
                    )
                    session.add(mem)
                    await session.flush()
        await session.commit()

        # 4. Create or fetch Travel Assistant Agent
        agent_res = await session.execute(
            select(Agent).where(
                Agent.organization_id == org.id,
                Agent.name == "Travel Assistant Agent",
            )
        )
        agent = agent_res.scalar_one_or_none()
        if agent is None:
            agent = Agent(
                organization_id=org.id,
                name="Travel Assistant Agent",
                slug="travel-assistant-agent",
                agent_type=AgentType.assistant.value,
                environment=AgentEnvironment.development.value,
                description="Autonomous customer travel booking assistant for flights, hotels, and itineraries",
                status=AgentStatus.active.value,
            )
            session.add(agent)
            await session.flush()
            print(f"[custode-demo] Registered Agent: {agent.name} (ID: {agent.id})")
        else:
            print(f"[custode-demo] Reusing Agent: {agent.name} (ID: {agent.id})")

        # 5. Create or fetch Booking Management Tool
        tool_slug = "booking_tool"
        tool_res = await session.execute(
            select(Tool).where(
                Tool.organization_id == org.id,
                Tool.slug == tool_slug,
            )
        )
        tool = tool_res.scalar_one_or_none()
        if tool is None:
            tool = Tool(
                organization_id=org.id,
                name="Booking Management Tool",
                slug=tool_slug,
                tool_type=ToolType.api.value,
                environment=ToolEnvironment.development.value,
                description="Production booking management API for room availability, reservations, and cancellations",
                endpoint="https://api.booking.internal/v1",
                status=ToolStatus.active.value,
            )
            session.add(tool)
            await session.flush()
            print(f"[custode-demo] Registered Tool: {tool.name} (ID: {tool.id})")
        else:
            print(f"[custode-demo] Reusing Tool: {tool.name} (ID: {tool.id})")

        # 6. Create Tool Operations
        # Op 1: search_available_rooms
        op_search_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "search_available_rooms",
            )
        )
        op_search = op_search_res.scalar_one_or_none()
        if op_search is None:
            op_search = ToolOperation(
                tool_id=tool.id,
                name="Search Available Rooms",
                slug="search_available_rooms",
                operation_type=OperationType.read.value,
                risk_level=OperationRiskLevel.low.value,
                description="Query available rooms and rates without booking commitment",
                status=OperationStatus.active.value,
            )
            session.add(op_search)
            await session.flush()

        # Op 2: cancel_booking
        op_cancel_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "cancel_booking",
            )
        )
        op_cancel = op_cancel_res.scalar_one_or_none()
        if op_cancel is None:
            op_cancel = ToolOperation(
                tool_id=tool.id,
                name="Cancel Existing Booking",
                slug="cancel_booking",
                operation_type=OperationType.write.value,
                risk_level=OperationRiskLevel.medium.value,
                description="Cancel an existing customer reservation",
                status=OperationStatus.active.value,
            )
            session.add(op_cancel)
            await session.flush()

        # Op 3: create_booking
        op_create_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "create_booking",
            )
        )
        op_create = op_create_res.scalar_one_or_none()
        if op_create is None:
            op_create = ToolOperation(
                tool_id=tool.id,
                name="Create Hotel Booking",
                slug="create_booking",
                operation_type=OperationType.write.value,
                risk_level=OperationRiskLevel.high.value,
                description="Authorize and commit funds for a hotel reservation",
                status=OperationStatus.active.value,
            )
            session.add(op_create)
            await session.flush()

        # 7. Configure Permissions
        # Allow search_available_rooms
        p_search_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_search.id,
            )
        )
        if p_search_res.scalar_one_or_none() is None:
            p_search = Permission(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=tool.id,
                operation_id=op_search.id,
                environment=ToolEnvironment.development.value,
                effect=PermissionEffect.allow.value,
                status=PermissionStatus.active.value,
            )
            session.add(p_search)

        # Deny cancel_booking
        p_cancel_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_cancel.id,
            )
        )
        if p_cancel_res.scalar_one_or_none() is None:
            p_cancel = Permission(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=tool.id,
                operation_id=op_cancel.id,
                environment=ToolEnvironment.development.value,
                effect=PermissionEffect.deny.value,
                status=PermissionStatus.active.value,
            )
            session.add(p_cancel)

        # Allow create_booking
        p_create_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_create.id,
            )
        )
        if p_create_res.scalar_one_or_none() is None:
            p_create = Permission(
                organization_id=org.id,
                agent_id=agent.id,
                tool_id=tool.id,
                operation_id=op_create.id,
                environment=ToolEnvironment.development.value,
                effect=PermissionEffect.allow.value,
                status=PermissionStatus.active.value,
            )
            session.add(p_create)

        await session.flush()
        await session.commit()

        # 8. Create Policy & Policy Version
        policy_res = await session.execute(
            select(Policy).where(
                Policy.organization_id == org.id,
                Policy.name == "High-Value Booking Guardrail",
            )
        )
        policy = policy_res.scalar_one_or_none()
        if policy is None:
            policy = await create_policy(
                session,
                org.id,
                PolicyCreate(
                    name="High-Value Booking Guardrail",
                    description="Mandates human security authorization for hotel bookings exceeding $500",
                    enforcement_mode=EnforcementMode.enforce,
                ),
            )
            v1 = await create_policy_version(
                session,
                org.id,
                policy.id,
                PolicyVersionCreate(
                    rules=[
                        PolicyRule(
                            name="Require Approval for Bookings > $500",
                            effect="require_approval",
                            conditions=[
                                PolicyRuleCondition(
                                    field="action.amount",
                                    operator="gt",
                                    value=500,
                                )
                            ],
                        )
                    ]
                ),
            )
            await publish_policy_version(session, org.id, policy.id, v1.id)
            await session.commit()
            print(f"[custode-demo] Configured and published Policy: {policy.name}")
        else:
            print(f"[custode-demo] Reusing Policy: {policy.name}")

        # 9. Execute Scenario A: Allowed Action (search_available_rooms)
        print("[custode-demo] Executing Scenario A: Allowed Room Search...")
        action_a = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_search.id,
                action_type="search_rooms",
                environment="dev",
                resource="/destinations/paris/rooms",
                resource_type="hotel_inventory",
                parameters={"city": "Paris", "check_in": "2026-11-01", "check_out": "2026-11-05", "guests": 2},
            ),
        )
        dec_a = await decide_runtime_action(session, org.id, action_a.id)
        exec_a = await execute_runtime_action(session, org.id, action_a.id)
        await session.commit()
        print(f"  -> Scenario A Action: {action_a.id}")
        print(f"  -> Decision: {dec_a.decision.upper()} | Execution: {exec_a.status.upper()}")

        # 10. Execute Scenario B: Blocked Action (cancel_booking)
        print("[custode-demo] Executing Scenario B: Blocked Cancellation (Missing/Denied Permission)...")
        action_b = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_cancel.id,
                action_type="cancel_reservation",
                environment="dev",
                resource="/reservations/RES-448291",
                resource_type="customer_reservation",
                parameters={"reservation_id": "RES-448291", "reason": "unauthorized_customer_request"},
            ),
        )
        dec_b = await decide_runtime_action(session, org.id, action_b.id)
        exec_b = await execute_runtime_action(session, org.id, action_b.id)
        await session.commit()
        print(f"  -> Scenario B Action: {action_b.id}")
        print(f"  -> Decision: {dec_b.decision.upper()} | Execution: {exec_b.status.upper()}")

        # 11. Execute Scenario C: High-Value Booking ($1,250.00 -> REQUIRE_APPROVAL)
        print("[custode-demo] Executing Scenario C: High-Value Booking ($1,250 -> Require Approval)...")
        action_c = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_create.id,
                action_type="book_hotel",
                environment="dev",
                resource="/bookings/hotel_resort_78",
                resource_type="financial_reservation",
                amount=1250.00,
                currency="USD",
                parameters={
                    "hotel_id": "HTL-771",
                    "room_type": "penthouse_suite",
                    "nights": 3,
                    "amount": 1250,
                    "currency": "USD",
                },
            ),
        )
        dec_c = await decide_runtime_action(session, org.id, action_c.id)
        appr_c = await create_approval_request(
            session=session,
            organization_id=org.id,
            runtime_action_id=action_c.id,
            data=ApprovalCreate(
                decision_id=dec_c.id,
                reason="High-value hotel reservation commitment of $1,250.00 requires authorized human review.",
            ),
        )
        await session.commit()
        print(f"  -> Scenario C Action: {action_c.id}")
        print(f"  -> Decision: {dec_c.decision.upper()} | Approval Request: {appr_c.id} (Status: {appr_c.status.upper()})")

        exec_c_status = "PENDING_APPROVAL"
        if approve_scenario_c and admin_user:
            print("[custode-demo] --approve-c flag active: Approving and executing Scenario C...")
            await approve_request(
                session=session,
                organization_id=org.id,
                approval_id=appr_c.id,
                reviewer_user_id=admin_user.id,
                data=ApprovalApproveRequest(reviewer_note="Executive travel authorized by Security Admin."),
            )
            exec_c = await execute_runtime_action(session, org.id, action_c.id)
            await session.commit()
            exec_c_status = exec_c.status.upper()
            print(f"  -> Execution: {exec_c_status}")

        print("\n" + "=" * 70)
        print("CUSTODE DEMONSTRATION SEEDING COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"Organization:       {org.name} ({org.slug})")
        print(f"Tenant ID:          {org.id}")
        print(f"Agent:              {agent.name} ({agent.id})")
        print(f"Tool:               {tool.name} ({tool.slug})")
        print(f"Scenario A (Allow): Action {action_a.id} -> {dec_a.decision.upper()} -> {exec_a.status.upper()}")
        print(f"Scenario B (Block): Action {action_b.id} -> {dec_b.decision.upper()} -> {exec_b.status.upper()}")
        print(f"Scenario C (Gov):   Action {action_c.id} -> {dec_c.decision.upper()} -> {appr_c.status.upper()} -> {exec_c_status}")
        print("-" * 70)
        print("Next steps for presenter/evaluator:")
        print("1. Open frontend at http://localhost:5173")
        print("2. Log in as security.admin@custode.io (Password: Custode#2026Admin!)")
        print("3. In the top navbar, select organization: 'Acme Travel AI'")
        print("4. Inspect Runtime Actions, Approvals Inbox, Executions, and Audit Logs.")
        print("=" * 70 + "\n")

        return {
            "organization_id": str(org.id),
            "organization_slug": org.slug,
            "agent_id": str(agent.id),
            "tool_id": str(tool.id),
            "scenario_a_action_id": str(action_a.id),
            "scenario_b_action_id": str(action_b.id),
            "scenario_c_action_id": str(action_c.id),
            "scenario_c_approval_id": str(appr_c.id),
        }


def main():
    parser = argparse.ArgumentParser(description="Seed CUSTODE Acme Travel AI demonstration scenario.")
    parser.add_argument(
        "--approve-c",
        action="store_true",
        help="Automatically approve and execute Scenario C instead of leaving it pending in the Approval Inbox.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(seed_demo_environment(approve_scenario_c=args.approve_c))
    finally:
        asyncio.run(close_engine())


if __name__ == "__main__":
    main()
