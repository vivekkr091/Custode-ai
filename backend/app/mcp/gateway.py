"""Authoritative CUSTODE MCP Security Gateway.

Mediates all Agent and Tool interactions across external MCP server boundaries:
1. Untrusted MCP Tool Discovery & Schema Fingerprinting (SHA-256 canonical hashing)
2. Tool Description Sentinel Security Scanning (Prompt injection, covert channels, secrets)
3. Schema Drift & Tool Poisoning Detection (Suspension on unapproved drift)
4. Runtime Tool Call Authorization (Permission -> Policy -> Risk -> Decision)
5. Input Argument Security Scanning (Sentinel)
6. Controlled Execution via Safe MCP Transports (HTTP JSON-RPC / Mock)
7. Output Response Security Scanning (Secret leak prevention, PII, vulnerability redaction)
8. Comprehensive Audit Trail & Telemetry
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditActorType, AuditEventType, AuditOutcome, record_event
from app.db.base import utc_now
from app.db.models.agent import Agent, AgentEnvironment, AgentStatus
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.decision import Decision
from app.db.models.mcp_server import MCPServer, MCPServerStatus
from app.db.models.mcp_tool import MCPTool, MCPToolStatus
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import ActionEnvironment, ActionStatus, RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.tool import Tool
from app.db.models.tool_operation import ToolOperation
from app.engines.decision.evaluator import DecisionEngine
from app.engines.permission.evaluator import PermissionEngine, PermissionRequest
from app.engines.risk.evaluator import RiskEngine
from app.mcp.exceptions import (
    MCPSchemaDriftError,
    MCPServerInactiveError,
    MCPServerNotFoundError,
    MCPToolInactiveError,
    MCPToolNotFoundError,
    MCPTransportError,
    MCPUnsupportedTransportError,
)
from app.mcp.policy import (
    build_mcp_action_context,
    evaluate_mcp_security_policy,
)
from app.mcp.registry import MCPRegistryService, _slugify
from app.mcp.sanitizer import compute_schema_hash, sanitize_description_text
from app.mcp.schemas import (
    MCPDiscoveryResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolResponse,
)
from app.mcp.security import (
    detect_schema_drift,
    scan_mcp_input_arguments,
    scan_mcp_output_result,
    scan_mcp_tool_description,
)
from app.mcp.transport import HttpMCPTransport, MockMCPTransport
from app.mcp.validator import validate_mcp_tool_arguments, validate_mcp_tool_schema
from app.schemas.approval import ApprovalCreate
from app.services.agent import create_agent, AgentCreate
from app.services.approval import create_approval_request

logger = logging.getLogger(__name__)


async def _audit_mcp_gateway(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    organization_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    agent_id: Optional[uuid.UUID] = None,
    resource_type: str = "MCP_SERVER",
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Any:
    meta = dict(metadata or {})
    if reason:
        meta["reason"] = reason

    actor_type = AuditActorType.AGENT if agent_id else (AuditActorType.USER if user_id else AuditActorType.SYSTEM)
    actor_id = str(agent_id) if agent_id else (str(user_id) if user_id else "custode_mcp_gateway")
    actor_display = f"Agent {agent_id}" if agent_id else (f"User {user_id}" if user_id else "CUSTODE MCP Gateway")

    return await record_event(
        session=session,
        event_type=event_type,
        action=action,
        organization_id=organization_id,
        user_id=user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_display=actor_display,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=meta,
        request_id=request_id,
    )


class MCPGateway:
    """Production-grade MCP Security Gateway orchestrating discovery, verification, and controlled execution."""

    @classmethod
    async def discover_server_tools(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        server_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        request_id: Optional[str] = None,
    ) -> MCPDiscoveryResponse:
        """Query an untrusted MCP server, fingerprint schemas, detect drift, and scan for security threats."""
        server = await MCPRegistryService.get_server(session, organization_id, server_id)

        if server.status != MCPServerStatus.ACTIVE.value:
            raise MCPServerInactiveError(server.id, server.status)

        await _audit_mcp_gateway(
            session=session,
            event_type=AuditEventType.MCP_DISCOVERY_STARTED,
            action="DISCOVER_MCP_TOOLS",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"endpoint": server.endpoint, "transport": server.transport},
            request_id=request_id,
        )

        # 1. Resolve safe transport
        if server.transport.upper() == "STDIO":
            raise MCPUnsupportedTransportError("STDIO")

        if server.transport.upper() == "MOCK" or server.endpoint.startswith("mock://"):
            transport = MockMCPTransport(server_id=server.id, server_name=server.name)
        else:
            transport = HttpMCPTransport(server.endpoint)

        # 2. Fetch remote tool definitions
        try:
            raw_tools = await transport.list_tools()
        except Exception as exc:
            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_DISCOVERY_FAILED,
                action="DISCOVER_MCP_TOOLS",
                organization_id=organization_id,
                user_id=user_id,
                resource_type="MCP_SERVER",
                resource_id=server.id,
                outcome=AuditOutcome.FAILURE,
                reason=f"Failed to fetch tools from MCP server: {str(exc)}",
                request_id=request_id,
            )
            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_TRANSPORT_ERROR,
                action="MCP_TRANSPORT_LIST_TOOLS",
                organization_id=organization_id,
                user_id=user_id,
                resource_type="MCP_SERVER",
                resource_id=server.id,
                outcome=AuditOutcome.FAILURE,
                reason=str(exc),
                request_id=request_id,
            )
            raise MCPTransportError(f"Failed to communicate with MCP server '{server.name}': {str(exc)}")

        discovered_count = len(raw_tools)
        new_tools_count = 0
        updated_tools_count = 0
        schema_drift_count = 0
        total_findings = 0

        mcp_tools_list: List[MCPTool] = []
        serialized_findings: List[Dict[str, Any]] = []

        # 3. Process and fingerprint each tool
        for raw_tool in raw_tools:
            # Validate tool structure
            validated_tool = validate_mcp_tool_schema(raw_tool)
            tool_name = validated_tool["name"]
            sanitized_description = sanitize_description_text(validated_tool.get("description", ""))
            input_schema = validated_tool.get("inputSchema") or validated_tool.get("input_schema") or {"type": "object", "properties": {}}
            output_schema = validated_tool.get("outputSchema") or validated_tool.get("output_schema")

            canonical_hash = compute_schema_hash(input_schema)

            # Sentinel security scan of untrusted description
            description_findings = scan_mcp_tool_description(
                description=sanitized_description,
                tool_name=tool_name,
                server_id=server.id,
            )

            # Check if tool already exists in tenant context
            existing_tool_q = select(MCPTool).where(
                MCPTool.organization_id == organization_id,
                MCPTool.mcp_server_id == server.id,
                MCPTool.name == tool_name,
            )
            existing_res = await session.execute(existing_tool_q)
            existing_tool = existing_res.scalar_one_or_none()

            if existing_tool is not None:
                # Check for schema drift
                is_drift = detect_schema_drift(existing_tool.schema_hash, canonical_hash)
                if is_drift:
                    existing_tool.previous_schema_hash = existing_tool.schema_hash
                    existing_tool.schema_hash = canonical_hash
                    existing_tool.schema_changed = True
                    existing_tool.input_schema = input_schema
                    existing_tool.description = sanitized_description
                    if output_schema:
                        existing_tool.output_schema = output_schema

                    # Prevent execution of mutated tool until operator re-activation
                    if existing_tool.status == MCPToolStatus.ACTIVE.value:
                        existing_tool.status = MCPToolStatus.SUSPENDED.value

                    schema_drift_count += 1

                    await _audit_mcp_gateway(
                        session=session,
                        event_type=AuditEventType.MCP_TOOL_SCHEMA_CHANGED,
                        action="DETECT_SCHEMA_DRIFT",
                        organization_id=organization_id,
                        user_id=user_id,
                        resource_type="MCP_TOOL",
                        resource_id=existing_tool.id,
                        outcome=AuditOutcome.SUCCESS,
                        reason="Schema hash changed between discovery runs",
                        metadata={
                            "tool_name": tool_name,
                            "previous_hash": existing_tool.previous_schema_hash,
                            "new_hash": canonical_hash,
                        },
                        request_id=request_id,
                    )
                else:
                    existing_tool.input_schema = input_schema
                    existing_tool.description = sanitized_description

                existing_tool.updated_at = utc_now()
                await session.flush()
                target_tool = existing_tool
                updated_tools_count += 1
            else:
                # Brand new discovered tool (Default status is always DISCOVERED)
                base_tool_slug = f"{server.slug}-{_slugify(tool_name)}"
                new_mcp_tool = MCPTool(
                    organization_id=organization_id,
                    mcp_server_id=server.id,
                    name=tool_name,
                    slug=base_tool_slug,
                    description=sanitized_description,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    status=MCPToolStatus.DISCOVERED.value,
                    risk_level="medium",
                    schema_hash=canonical_hash,
                    previous_schema_hash=None,
                    schema_changed=False,
                    discovered_at=utc_now(),
                    tool_metadata={"raw_name": tool_name},
                )
                session.add(new_mcp_tool)
                await session.flush()
                target_tool = new_mcp_tool
                new_tools_count += 1

                await _audit_mcp_gateway(
                    session=session,
                    event_type=AuditEventType.MCP_TOOL_DISCOVERED,
                    action="DISCOVER_MCP_TOOL",
                    organization_id=organization_id,
                    user_id=user_id,
                    resource_type="MCP_TOOL",
                    resource_id=target_tool.id,
                    outcome=AuditOutcome.SUCCESS,
                    metadata={
                        "tool_name": tool_name,
                        "schema_hash": canonical_hash,
                        "status": MCPToolStatus.DISCOVERED.value,
                    },
                    request_id=request_id,
                )

            # Persist description findings
            for n_find in description_findings:
                finding_sev = n_find.severity.value if hasattr(n_find.severity, "value") else str(n_find.severity)
                sf = SecurityFinding(
                    organization_id=organization_id,
                    mcp_server_id=server.id,
                    mcp_tool_id=target_tool.id,
                    runtime_action_id=None,
                    scanner=n_find.scanner,
                    category=n_find.category,
                    severity=finding_sev,
                    title=n_find.title,
                    description=n_find.description,
                    evidence=n_find.evidence,
                    remediation=n_find.remediation,
                    source="MCP_TOOL_DESCRIPTION",
                    finding_metadata=n_find.metadata,
                )
                session.add(sf)
                total_findings += 1
                serialized_findings.append({
                    "scanner": n_find.scanner,
                    "category": n_find.category,
                    "severity": finding_sev,
                    "title": n_find.title,
                    "description": n_find.description,
                    "remediation": n_find.remediation,
                    "tool_name": tool_name,
                })

            mcp_tools_list.append(target_tool)

        # Update server last_discovered_at
        server.last_discovered_at = utc_now()
        await session.flush()

        await _audit_mcp_gateway(
            session=session,
            event_type=AuditEventType.MCP_DISCOVERY_COMPLETED,
            action="DISCOVER_MCP_TOOLS",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="MCP_SERVER",
            resource_id=server.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "discovered_count": discovered_count,
                "new_tools_count": new_tools_count,
                "updated_tools_count": updated_tools_count,
                "schema_drift_count": schema_drift_count,
                "findings_count": total_findings,
            },
            request_id=request_id,
        )

        return MCPDiscoveryResponse(
            server_id=server.id,
            discovered_count=discovered_count,
            new_tools_count=new_tools_count,
            updated_tools_count=updated_tools_count,
            schema_drift_count=schema_drift_count,
            findings_count=total_findings,
            tools=[MCPToolResponse.model_validate(t) for t in mcp_tools_list],
            findings=serialized_findings,
        )

    @classmethod
    async def _resolve_execution_agent(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        agent_id: Optional[uuid.UUID] = None,
    ) -> Agent:
        """Resolve a valid, active Agent identity for the MCP tool execution."""
        if agent_id:
            agent_q = select(Agent).where(
                Agent.id == agent_id,
                Agent.organization_id == organization_id,
            )
            agent_res = await session.execute(agent_q)
            agent = agent_res.scalar_one_or_none()
            if agent and agent.status == AgentStatus.active.value:
                return agent

        # Try to find any active agent in the organization
        existing_agent_q = select(Agent).where(
            Agent.organization_id == organization_id,
            Agent.status == AgentStatus.active.value,
        ).limit(1)
        res = await session.execute(existing_agent_q)
        agent = res.scalar_one_or_none()
        if agent is not None:
            return agent

        # Create a standard system caller agent for this tenant
        new_agent = Agent(
            organization_id=organization_id,
            name="MCP Gateway System Agent",
            slug=f"mcp-gateway-agent-{str(organization_id)[:8]}",
            description="Authoritative identity for MCP Gateway tool invocations",
            agent_type="system",
            environment=AgentEnvironment.production.value,
            status=AgentStatus.active.value,
        )
        session.add(new_agent)
        await session.flush()
        return new_agent

    @classmethod
    async def execute_tool_call(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        tool_id: uuid.UUID,
        arguments: Dict[str, Any],
        agent_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        request_id: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> MCPToolCallResponse:
        """Execute a controlled MCP tool invocation through CUSTODE's full security pipeline."""
        start_time = time.perf_counter()
        req_id = request_id or str(uuid.uuid4())

        # 1. Fetch MCP Tool & Server
        mcp_tool = await MCPRegistryService.get_tool(session, organization_id, tool_id)
        server = await MCPRegistryService.get_server(session, organization_id, mcp_tool.mcp_server_id)

        # 2. Server Status Check
        if server.status != MCPServerStatus.ACTIVE.value:
            raise MCPServerInactiveError(server.id, server.status)

        # 3. Schema Drift Protection Check (Detects tool poisoning before standard status check)
        if mcp_tool.schema_changed:
            raise MCPSchemaDriftError(
                f"MCP Tool '{mcp_tool.name}' has unapproved schema drift. "
                "Operator review and re-activation required before execution."
            )

        # 4. Tool Status Check
        if mcp_tool.status != MCPToolStatus.ACTIVE.value:
            raise MCPToolInactiveError(mcp_tool.id, mcp_tool.status)

        # 5. Validate Arguments against input_schema
        validate_mcp_tool_arguments(arguments, mcp_tool.input_schema)

        # 6. Ensure mapping to CUSTODE Tool and ToolOperation
        if not mcp_tool.tool_id or not mcp_tool.operation_id:
            # Auto-map/activate mapping
            await MCPRegistryService.activate_tool(session, organization_id, mcp_tool.id, user_id=user_id)
            await session.refresh(mcp_tool)

        tool = await session.get(Tool, mcp_tool.tool_id)
        operation = await session.get(ToolOperation, mcp_tool.operation_id)
        if not tool or not operation:
            raise MCPToolNotFoundError(tool_id, organization_id)

        # 7. Resolve Agent Identity
        agent = await cls._resolve_execution_agent(session, organization_id, agent_id)

        await _audit_mcp_gateway(
            session=session,
            event_type=AuditEventType.MCP_TOOL_CALL_RECEIVED,
            action="RECEIVE_MCP_TOOL_CALL",
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent.id,
            resource_type="MCP_TOOL",
            resource_id=mcp_tool.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"tool_name": mcp_tool.name, "server_name": server.name},
            request_id=req_id,
        )

        # 8. Create RuntimeAction representation
        act_env = ActionEnvironment.prod.value
        if environment:
            env_map = {"development": "dev", "dev": "dev", "staging": "staging", "production": "prod", "prod": "prod"}
            act_env = env_map.get(environment.lower(), ActionEnvironment.prod.value)

        action_req_uuid = uuid.UUID(str(req_id)) if not isinstance(req_id, uuid.UUID) else req_id
        action = RuntimeAction(
            organization_id=organization_id,
            agent_id=agent.id,
            tool_id=tool.id,
            operation_id=operation.id,
            action_type="mcp_tool_call",
            environment=act_env,
            parameters=arguments,
            request_id=action_req_uuid,
            status=ActionStatus.pending.value,
        )
        session.add(action)
        await session.flush()

        # 9. Scan input arguments with Sentinel
        input_findings = scan_mcp_input_arguments(
            arguments=arguments,
            tool_name=mcp_tool.name,
            agent_id=agent.id,
            server_id=server.id,
        )

        input_finding_records: List[SecurityFinding] = []
        for n_find in input_findings:
            sev = n_find.severity.value if hasattr(n_find.severity, "value") else str(n_find.severity)
            sf = SecurityFinding(
                organization_id=organization_id,
                mcp_server_id=server.id,
                mcp_tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                scanner=n_find.scanner,
                category=n_find.category,
                severity=sev,
                title=n_find.title,
                description=n_find.description,
                evidence=n_find.evidence,
                remediation=n_find.remediation,
                source="MCP_INPUT",
                finding_metadata=n_find.metadata,
            )
            session.add(sf)
            input_finding_records.append(sf)
        await session.flush()

        serialized_input_findings = [
            {
                "id": str(f.id),
                "scanner": f.scanner,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "remediation": f.remediation,
            }
            for f in input_finding_records
        ]

        # 10. Authoritative CUSTODE Control Plane Pipeline
        # (a) Permission Check
        perm_env_map = {"dev": "development", "staging": "staging", "prod": "production"}
        perm_req = PermissionRequest(
            organization_id=organization_id,
            agent_id=agent.id,
            tool_id=tool.id,
            operation_id=operation.id,
            environment=perm_env_map.get(action.environment, "production"),
        )
        perm_result = await PermissionEngine.evaluate(session, perm_req)

        # (b) Policy Check
        action_context = build_mcp_action_context(
            agent_id=agent.id,
            agent_environment=agent.environment.value if hasattr(agent.environment, "value") else str(agent.environment),
            tool_id=tool.id,
            operation_id=operation.id,
            mcp_server_id=server.id,
            mcp_server_trust_level=server.trust_level,
            mcp_tool_id=mcp_tool.id,
            mcp_tool_slug=mcp_tool.slug,
            schema_hash=mcp_tool.schema_hash,
            risk_level=operation.risk_level or "medium",
            request_id=req_id,
        )
        policy_result = await evaluate_mcp_security_policy(session, organization_id, action_context)

        # (c) Contextual Risk Assessment
        risk_result = RiskEngine.evaluate(
            runtime_action=action,
            operation_baseline_risk_level=operation.risk_level,
            operation_type=operation.operation_type,
            security_findings=input_finding_records,
        )

        # (d) Decision Arbitration
        decision_eval = DecisionEngine.evaluate(
            permission_result=perm_result,
            policy_result=policy_result,
            risk_result=risk_result,
            security_findings=input_finding_records,
        )

        # Persist Decision record
        decision_val = decision_eval.decision.value if hasattr(decision_eval.decision, "value") else str(decision_eval.decision)
        decision_record = Decision(
            organization_id=organization_id,
            runtime_action_id=action.id,
            decision=decision_val,
            reason=decision_eval.reason,
            risk_level=decision_eval.risk_level,
            risk_score=decision_eval.risk_score,
            permission_effect=decision_eval.permission_effect,
            policy_effect=decision_eval.policy_effect,
            policy_id=decision_eval.policy_id,
            policy_version_id=decision_eval.policy_version_id,
            factors=[f.model_dump() if hasattr(f, "model_dump") else f for f in decision_eval.factors],
            evaluation_trace=decision_eval.evaluation_trace,
            engine_version=decision_eval.engine_version,
            evaluated_at=utc_now(),
        )
        session.add(decision_record)
        await session.flush()

        # 11. Handle Decision Branching
        # CASE 1: BLOCK / DENY
        if decision_val in ("block", "deny"):
            action.status = ActionStatus.denied.value
            await session.flush()

            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_TOOL_CALL_BLOCKED,
                action="BLOCK_MCP_TOOL_CALL",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="MCP_TOOL",
                resource_id=mcp_tool.id,
                outcome=AuditOutcome.DENIED,
                reason=decision_eval.reason,
                metadata={"findings_count": len(input_finding_records), "decision": decision_val},
                request_id=req_id,
            )

            latency = (time.perf_counter() - start_time) * 1000.0
            return MCPToolCallResponse(
                tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                decision="block",
                status="blocked",
                result=None,
                approval_id=None,
                latency_ms=latency,
                input_findings=serialized_input_findings,
                output_findings=[],
                error=decision_eval.reason,
            )

        # CASE 2: REQUIRE_APPROVAL
        if decision_val == "require_approval":
            approval = await create_approval_request(
                session=session,
                organization_id=organization_id,
                runtime_action_id=action.id,
                data=ApprovalCreate(
                    decision_id=decision_record.id,
                    reason=decision_eval.reason,
                ),
            )
            action.status = ActionStatus.pending.value
            await session.flush()

            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_TOOL_CALL_APPROVAL_REQUIRED,
                action="REQUIRE_MCP_TOOL_APPROVAL",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="MCP_TOOL",
                resource_id=mcp_tool.id,
                outcome=AuditOutcome.SUCCESS,
                reason=decision_eval.reason,
                metadata={"approval_id": str(approval.id)},
                request_id=req_id,
            )

            latency = (time.perf_counter() - start_time) * 1000.0
            return MCPToolCallResponse(
                tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                decision="require_approval",
                status="approval_required",
                result=None,
                approval_id=approval.id,
                latency_ms=latency,
                input_findings=serialized_input_findings,
                output_findings=[],
                error=decision_eval.reason,
            )

        # CASE 3: ALLOW -> Execute Tool via Safe Transport
        action.status = ActionStatus.approved.value
        await session.flush()

        if server.transport.upper() == "MOCK" or server.endpoint.startswith("mock://"):
            transport = MockMCPTransport(server_id=server.id, server_name=server.name)
        else:
            transport = HttpMCPTransport(server.endpoint)

        try:
            raw_result = await transport.call_tool(mcp_tool.name, arguments)
        except Exception as exc:
            action.status = ActionStatus.failed.value
            await session.flush()

            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_TRANSPORT_ERROR,
                action="EXECUTE_MCP_TOOL",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="MCP_TOOL",
                resource_id=mcp_tool.id,
                outcome=AuditOutcome.FAILURE,
                reason=str(exc),
                request_id=req_id,
            )

            latency = (time.perf_counter() - start_time) * 1000.0
            return MCPToolCallResponse(
                tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                decision="allow",
                status="failed",
                result=None,
                approval_id=None,
                latency_ms=latency,
                input_findings=serialized_input_findings,
                output_findings=[],
                error=f"MCP Transport invocation failed: {str(exc)}",
            )

        # 12. Scan Output with Sentinel
        output_findings = scan_mcp_output_result(
            result=raw_result,
            tool_name=mcp_tool.name,
            server_id=server.id,
        )

        output_finding_records: List[SecurityFinding] = []
        has_critical_output_finding = False

        for n_find in output_findings:
            sev_raw = n_find.severity.value if hasattr(n_find.severity, "value") else str(n_find.severity)
            sev = sev_raw.lower()
            cat_raw = n_find.category.value if hasattr(n_find.category, "value") else str(n_find.category)
            cat = cat_raw.lower()

            if sev in ("critical", "high") and (
                n_find.scanner in ("secrets_scanner", "harmful_content", "pii", "code_scanner")
                or "secret" in cat
                or "pii" in cat
            ):
                has_critical_output_finding = True

            sf = SecurityFinding(
                organization_id=organization_id,
                mcp_server_id=server.id,
                mcp_tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                scanner=n_find.scanner,
                category=n_find.category,
                severity=sev,
                title=n_find.title,
                description=n_find.description,
                evidence=n_find.evidence,
                remediation=n_find.remediation,
                source="MCP_OUTPUT",
                finding_metadata=n_find.metadata,
            )
            session.add(sf)
            output_finding_records.append(sf)
        await session.flush()

        await _audit_mcp_gateway(
            session=session,
            event_type=AuditEventType.MCP_TOOL_RESULT_SCANNED,
            action="SCAN_MCP_TOOL_OUTPUT",
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent.id,
            resource_type="MCP_TOOL",
            resource_id=mcp_tool.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"findings_count": len(output_finding_records)},
            request_id=req_id,
        )

        serialized_output_findings = [
            {
                "id": str(f.id),
                "scanner": f.scanner,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "description": f.description,
                "remediation": f.remediation,
            }
            for f in output_finding_records
        ]

        latency = (time.perf_counter() - start_time) * 1000.0

        # If critical output vulnerability / secret leak detected: BLOCK RESPONSE
        if has_critical_output_finding:
            action.status = ActionStatus.denied.value
            await session.flush()

            await _audit_mcp_gateway(
                session=session,
                event_type=AuditEventType.MCP_TOOL_RESULT_BLOCKED,
                action="BLOCK_MCP_TOOL_RESULT",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="MCP_TOOL",
                resource_id=mcp_tool.id,
                outcome=AuditOutcome.DENIED,
                reason="MCP tool response blocked due to sensitive secret leakage or critical vulnerability",
                metadata={"findings_count": len(output_finding_records)},
                request_id=req_id,
            )

            return MCPToolCallResponse(
                tool_id=mcp_tool.id,
                runtime_action_id=action.id,
                decision="block",
                status="blocked",
                result=None,
                approval_id=None,
                latency_ms=latency,
                input_findings=serialized_input_findings,
                output_findings=serialized_output_findings,
                error="Output blocked by CUSTODE: sensitive data or critical vulnerability detected in tool response.",
            )

        # Execution succeeded cleanly!
        action.status = ActionStatus.executed.value
        await session.flush()

        await _audit_mcp_gateway(
            session=session,
            event_type=AuditEventType.MCP_TOOL_CALL_EXECUTED,
            action="EXECUTE_MCP_TOOL",
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent.id,
            resource_type="MCP_TOOL",
            resource_id=mcp_tool.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"latency_ms": latency},
            request_id=req_id,
        )

        return MCPToolCallResponse(
            tool_id=mcp_tool.id,
            runtime_action_id=action.id,
            decision="allow",
            status="executed",
            result=raw_result,
            approval_id=None,
            latency_ms=latency,
            input_findings=serialized_input_findings,
            output_findings=serialized_output_findings,
            error=None,
        )
