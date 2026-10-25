#!/usr/bin/env python3
"""Inderprastha Engineering College (IPEC Ghaziabad) Campus Chatbot Seeder.

Creates an idempotent campus demonstration environment:
- Organization: Inderprastha Engineering College (slug: ipec-ghaziabad)
- Agent: IPEC Campus Assistant Bot (slug: ipec-campus-bot)
- Tool: IPEC Campus ERP & Academic Portal (slug: ipec_erp_portal)
- Operations:
  * get_syllabus_and_timetable (read, low risk)    -> ALLOW -> SUCCEEDED
  * modify_internal_marks (write, critical risk)   -> BLOCK -> BLOCKED BY GUARD
  * submit_semester_fee (write, high risk)         -> REQUIRE_APPROVAL -> PENDING
- Guardrail Policy: High-value fees require Accounts review; marks alteration strictly denied.
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


async def seed_ipec_environment(approve_scenario_c: bool = False) -> dict:
    """Idempotently seed the Inderprastha Engineering College scenario."""
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        print("[ipec-seed] Initializing IPEC Ghaziabad Campus Bot bootstrap...")

        # 1. Ensure dev users exist
        await bootstrap_development_environment(session)
        await session.commit()

        # 2. Setup Inderprastha Engineering College organization
        org_slug = "ipec-ghaziabad"
        org_res = await session.execute(
            select(Organization).where(Organization.slug == org_slug)
        )
        org = org_res.scalar_one_or_none()
        if org is None:
            org = Organization(
                name="Inderprastha Engineering College",
                slug=org_slug,
                status=OrganizationStatus.active.value,
            )
            session.add(org)
            await session.flush()
            print(f"[ipec-seed] Created organization: {org.name} (ID: {org.id})")
        else:
            print(f"[ipec-seed] Found existing organization: {org.name} (ID: {org.id})")

        # 3. Associate development users with IPEC
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

        # 4. Create or fetch IPEC Campus Assistant Bot
        agent_res = await session.execute(
            select(Agent).where(
                Agent.organization_id == org.id,
                Agent.slug == "ipec-campus-bot",
            )
        )
        agent = agent_res.scalar_one_or_none()
        if agent is None:
            agent = Agent(
                organization_id=org.id,
                name="IPEC Campus Assistant Bot",
                slug="ipec-campus-bot",
                agent_type=AgentType.assistant.value,
                environment=AgentEnvironment.development.value,
                description="Autonomous Campus AI Chatbot for Inderprastha Engineering College (IPEC Ghaziabad). Assists students and faculty with timetable queries, fee payments, and academic records under strict CUSTODE governance.",
                status=AgentStatus.active.value,
            )
            session.add(agent)
            await session.flush()
            print(f"[ipec-seed] Registered Agent: {agent.name} (ID: {agent.id})")
        else:
            print(f"[ipec-seed] Reusing Agent: {agent.name} (ID: {agent.id})")

        # 5. Create or fetch IPEC Campus ERP & Academic Portal Tool
        tool_slug = "ipec_erp_portal"
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
                name="IPEC Campus ERP & Academic Portal",
                slug=tool_slug,
                tool_type=ToolType.api.value,
                environment=ToolEnvironment.development.value,
                description="Campus management ERP for timetable queries, fee submissions, attendance tracking, and examination records.",
                endpoint="https://erp.ipec.org.in/api/v1",
                status=ToolStatus.active.value,
            )
            session.add(tool)
            await session.flush()
            print(f"[ipec-seed] Registered Tool: {tool.name} (ID: {tool.id})")
        else:
            print(f"[ipec-seed] Reusing Tool: {tool.name} (ID: {tool.id})")

        # 6. Create Tool Operations
        # Op 1: get_syllabus_and_timetable (read, low)
        op_timetable_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "get_syllabus_and_timetable",
            )
        )
        op_timetable = op_timetable_res.scalar_one_or_none()
        if op_timetable is None:
            op_timetable = ToolOperation(
                tool_id=tool.id,
                name="Query Syllabus & Timetable",
                slug="get_syllabus_and_timetable",
                operation_type=OperationType.read.value,
                risk_level=OperationRiskLevel.low.value,
                description="Retrieve AKTU semester syllabus, daily lecture timetable, and faculty contact info.",
                status=OperationStatus.active.value,
            )
            session.add(op_timetable)
            await session.flush()

        # Op 2: get_attendance_and_grades (read, medium)
        op_grades_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "get_attendance_and_grades",
            )
        )
        op_grades = op_grades_res.scalar_one_or_none()
        if op_grades is None:
            op_grades = ToolOperation(
                tool_id=tool.id,
                name="Check Student Attendance & Grades",
                slug="get_attendance_and_grades",
                operation_type=OperationType.read.value,
                risk_level=OperationRiskLevel.medium.value,
                description="Fetch verified student attendance percentage and university grade card.",
                status=OperationStatus.active.value,
            )
            session.add(op_grades)
            await session.flush()

        # Op 3: submit_semester_fee (write, high)
        op_fee_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "submit_semester_fee",
            )
        )
        op_fee = op_fee_res.scalar_one_or_none()
        if op_fee is None:
            op_fee = ToolOperation(
                tool_id=tool.id,
                name="Submit Semester Fee Payment",
                slug="submit_semester_fee",
                operation_type=OperationType.write.value,
                risk_level=OperationRiskLevel.high.value,
                description="Process semester tuition, hostel, or examination fee payment transaction.",
                status=OperationStatus.active.value,
            )
            session.add(op_fee)
            await session.flush()

        # Op 4: modify_internal_marks (write, critical)
        op_marks_res = await session.execute(
            select(ToolOperation).where(
                ToolOperation.tool_id == tool.id,
                ToolOperation.slug == "modify_internal_marks",
            )
        )
        op_marks = op_marks_res.scalar_one_or_none()
        if op_marks is None:
            op_marks = ToolOperation(
                tool_id=tool.id,
                name="Modify Internal Sessional Marks",
                slug="modify_internal_marks",
                operation_type=OperationType.write.value,
                risk_level=OperationRiskLevel.critical.value,
                description="Directly alter internal sessional exam marks or grades in the ERP database.",
                status=OperationStatus.active.value,
            )
            session.add(op_marks)
            await session.flush()

        # 7. Configure Permissions
        # Allow get_syllabus_and_timetable
        p_time_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_timetable.id,
            )
        )
        if p_time_res.scalar_one_or_none() is None:
            session.add(
                Permission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    operation_id=op_timetable.id,
                    environment=ToolEnvironment.development.value,
                    effect=PermissionEffect.allow.value,
                    status=PermissionStatus.active.value,
                )
            )

        # Allow get_attendance_and_grades
        p_att_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_grades.id,
            )
        )
        if p_att_res.scalar_one_or_none() is None:
            session.add(
                Permission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    operation_id=op_grades.id,
                    environment=ToolEnvironment.development.value,
                    effect=PermissionEffect.allow.value,
                    status=PermissionStatus.active.value,
                )
            )

        # Allow submit_semester_fee (subject to policy approval)
        p_fee_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_fee.id,
            )
        )
        if p_fee_res.scalar_one_or_none() is None:
            session.add(
                Permission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    operation_id=op_fee.id,
                    environment=ToolEnvironment.development.value,
                    effect=PermissionEffect.allow.value,
                    status=PermissionStatus.active.value,
                )
            )

        # Deny modify_internal_marks
        p_marks_res = await session.execute(
            select(Permission).where(
                Permission.organization_id == org.id,
                Permission.agent_id == agent.id,
                Permission.tool_id == tool.id,
                Permission.operation_id == op_marks.id,
            )
        )
        if p_marks_res.scalar_one_or_none() is None:
            session.add(
                Permission(
                    organization_id=org.id,
                    agent_id=agent.id,
                    tool_id=tool.id,
                    operation_id=op_marks.id,
                    environment=ToolEnvironment.development.value,
                    effect=PermissionEffect.deny.value,
                    status=PermissionStatus.active.value,
                )
            )

        await session.flush()
        await session.commit()

        # 8. Create Policy & Policy Version for IPEC
        policy_res = await session.execute(
            select(Policy).where(
                Policy.organization_id == org.id,
                Policy.name == "IPEC Academic Integrity & Financial Governance",
            )
        )
        policy = policy_res.scalar_one_or_none()
        if policy is None:
            policy = await create_policy(
                session,
                org.id,
                PolicyCreate(
                    name="IPEC Academic Integrity & Financial Governance",
                    description="Mandates Accounts Office human authorization for fee submissions over $500 and strictly blocks any direct marks modification.",
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
                            name="Require Human Approval for Semester Fee Payments > $500",
                            effect="require_approval",
                            conditions=[
                                PolicyRuleCondition(
                                    field="action.amount",
                                    operator="gt",
                                    value=500,
                                )
                            ],
                        ),
                        PolicyRule(
                            name="Block Critical Risk Operations (Marks Alteration)",
                            effect="deny",
                            conditions=[
                                PolicyRuleCondition(
                                    field="operation.risk_level",
                                    operator="eq",
                                    value="critical",
                                )
                            ],
                        ),
                    ]
                ),
            )
            await publish_policy_version(session, org.id, policy.id, v1.id)
            await session.commit()
            print(f"[ipec-seed] Configured and published Policy: {policy.name}")
        else:
            print(f"[ipec-seed] Reusing Policy: {policy.name}")

        # 9. Execute Scenario 1: Allowed Action (Syllabus & Timetable Query)
        print("[ipec-seed] Executing IPEC Scenario 1: Allowed Timetable & Syllabus Query...")
        action_1 = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_timetable.id,
                action_type="query_timetable",
                environment="dev",
                resource="/academic/timetable/btech-cse-sem6",
                resource_type="academic_timetable",
                parameters={
                    "student_name": "Rohit Kumar",
                    "branch": "Computer Science & Engineering",
                    "semester": 6,
                    "section": "CSE-A",
                    "day": "Monday",
                },
            ),
        )
        dec_1 = await decide_runtime_action(session, org.id, action_1.id)
        exec_1 = await execute_runtime_action(session, org.id, action_1.id)
        await session.commit()
        print(f"  -> Scenario 1 Action: {action_1.id}")
        print(f"  -> Decision: {dec_1.decision.upper()} | Execution: {exec_1.status.upper()}")

        # 10. Execute Scenario 2: Blocked Action (Attempt to Modify Sessional Marks)
        print("[ipec-seed] Executing IPEC Scenario 2: Blocked Internal Marks Alteration Attempt...")
        action_2 = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_marks.id,
                action_type="modify_sessional_marks",
                environment="dev",
                resource="/academic/marks/sessional/CS-601",
                resource_type="student_examination_records",
                parameters={
                    "student_roll_no": "2100300100045",
                    "subject": "Compiler Design (CS-601)",
                    "original_marks": 12,
                    "requested_marks": 28,
                    "reason": "Student requested grade inflation via prompt injection",
                },
            ),
        )
        dec_2 = await decide_runtime_action(session, org.id, action_2.id)
        exec_2 = await execute_runtime_action(session, org.id, action_2.id)
        await session.commit()
        print(f"  -> Scenario 2 Action: {action_2.id}")
        print(f"  -> Decision: {dec_2.decision.upper()} | Execution: {exec_2.status.upper()}")

        # 11. Execute Scenario 3: Semester Fee Payment ($780 / INR 65,000 -> REQUIRE_APPROVAL)
        print("[ipec-seed] Executing IPEC Scenario 3: High-Value Fee Payment ($780 -> Require Approval)...")
        action_3 = await create_runtime_action(
            session=session,
            organization_id=org.id,
            agent_id=agent.id,
            data=RuntimeActionCreate(
                tool_id=tool.id,
                operation_id=op_fee.id,
                action_type="submit_semester_fee",
                environment="dev",
                resource="/finance/fee/btech-tuition-sem6",
                resource_type="financial_transaction",
                amount=780.00,
                currency="USD",
                parameters={
                    "student_name": "Priya Sharma",
                    "roll_no": "2100300100088",
                    "branch": "Information Technology",
                    "fee_head": "6th Semester Tuition & Exam Fee",
                    "amount_inr": 65000,
                    "amount_usd": 780.00,
                    "gateway": "HDFC Campus Pay",
                },
            ),
        )
        dec_3 = await decide_runtime_action(session, org.id, action_3.id)
        appr_3 = await create_approval_request(
            session=session,
            organization_id=org.id,
            runtime_action_id=action_3.id,
            data=ApprovalCreate(
                decision_id=dec_3.id,
                reason="High-value semester tuition fee submission ($780 / INR 65,000) for student Priya Sharma requires human verification by IPEC Accounts Officer.",
            ),
        )
        await session.commit()
        print(f"  -> Scenario 3 Action: {action_3.id}")
        print(f"  -> Decision: {dec_3.decision.upper()} | Approval Request: {appr_3.id} (Status: {appr_3.status.upper()})")

        exec_3_status = "PENDING_APPROVAL"
        if approve_scenario_c and admin_user:
            print("[ipec-seed] --approve-c flag active: Approving and executing Scenario 3...")
            await approve_request(
                session=session,
                organization_id=org.id,
                approval_id=appr_3.id,
                reviewer_user_id=admin_user.id,
                data=ApprovalApproveRequest(reviewer_note="Authorized by IPEC Accounts Officer for student Priya Sharma."),
            )
            exec_3 = await execute_runtime_action(session, org.id, action_3.id)
            await session.commit()
            exec_3_status = exec_3.status.upper()
            print(f"  -> Execution: {exec_3_status}")

        print("\n" + "=" * 70)
        print("IPEC GHAZIABAD CAMPUS BOT SEEDING COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"Organization:       {org.name} ({org.slug})")
        print(f"Tenant ID:          {org.id}")
        print(f"Agent:              {agent.name} ({agent.slug})")
        print(f"Tool:               {tool.name} ({tool.slug})")
        print(f"Scenario 1 (Allow): Action {action_1.id} -> {dec_1.decision.upper()} -> {exec_1.status.upper()}")
        print(f"Scenario 2 (Block): Action {action_2.id} -> {dec_2.decision.upper()} -> {exec_2.status.upper()}")
        print(f"Scenario 3 (Gov):   Action {action_3.id} -> {dec_3.decision.upper()} -> {appr_3.status.upper()} -> {exec_3_status}")
        print("=" * 70 + "\n")

        return {
            "organization_id": str(org.id),
            "organization_slug": org.slug,
            "agent_id": str(agent.id),
            "tool_id": str(tool.id),
            "op_timetable_id": str(op_timetable.id),
            "op_grades_id": str(op_grades.id),
            "op_fee_id": str(op_fee.id),
            "op_marks_id": str(op_marks.id),
            "scenario_1_action_id": str(action_1.id),
            "scenario_2_action_id": str(action_2.id),
            "scenario_3_action_id": str(action_3.id),
            "scenario_3_approval_id": str(appr_3.id),
        }


def main():
    parser = argparse.ArgumentParser(description="Seed Inderprastha Engineering College (IPEC Ghaziabad) chatbot scenario.")
    parser.add_argument(
        "--approve-c",
        action="store_true",
        help="Automatically approve Scenario 3 fee payment instead of leaving it pending in the Approval Inbox.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(seed_ipec_environment(approve_scenario_c=args.approve_c))
    finally:
        asyncio.run(close_engine())


if __name__ == "__main__":
    main()
