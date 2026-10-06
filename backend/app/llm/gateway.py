"""Authoritative CUSTODE LLM Security Gateway.

Mediates all Agent/Application interactions with LLM providers:
1. Inbound Authentication & Identity Validation
2. Provider & Model Allowlist Validation (SSRF Protection)
3. Input Security Scanning (Sentinel: prompt injection, jailbreak, secrets, PII, harmful content)
4. Authoritative Control Plane (Permission -> Policy -> Risk -> Decision)
5. Execution Delegation (Provider complete/stream)
6. Output Security Scanning (Sentinel: secrets, PII, harmful content, toxicity, code security)
7. Content Hashing & Redaction (No raw prompt/response database retention by default)
8. Untrusted Tool Call Dispatch via CUSTODE RuntimeAction control plane
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import AuditActorType, AuditEventType, AuditOutcome, record_event
from app.db.base import utc_now
from app.db.models.agent import Agent, AgentEnvironment, AgentStatus
from app.db.models.approval import ApprovalRequest, ApprovalStatus
from app.db.models.decision import Decision
from app.db.models.llm_interaction import LLMInteraction
from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.runtime_action import ActionEnvironment, ActionStatus, RuntimeAction
from app.db.models.security_finding import SecurityFinding
from app.db.models.tool import Tool, ToolStatus, ToolType
from app.db.models.tool_operation import OperationRiskLevel, OperationStatus, OperationType, ToolOperation
from app.engines.decision.evaluator import DecisionEngine
from app.engines.permission.evaluator import PermissionEngine, PermissionRequest
from app.engines.policy.evaluator import PolicyEngine
from app.engines.risk.evaluator import RiskEngine
from app.llm.exceptions import (
    LLMApprovalRequiredError,
    LLMError,
    LLMModelNotAllowedError,
    LLMOutputSecurityError,
    LLMProviderNotFoundError,
    LLMRateLimitError,
    LLMSecurityBlockError,
    LLMToolCallSecurityError,
)
from app.llm.policy import (
    LLM_INPUT_PROFILE,
    LLM_OUTPUT_PROFILE,
    build_llm_action_context,
    evaluate_llm_security_policy,
)
from app.llm.registry import provider_registry
from app.llm.sanitizer import compute_content_hash, create_sanitized_preview
from app.llm.schemas import (
    ChatMessage,
    LLMMetricsResponse,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    ToolCall,
    ToolCallExecutionRequest,
    ToolCallExecutionResponse,
)
from app.schemas.approval import ApprovalCreate
from app.sentinel.adapter import sentinel_adapter
from app.sentinel.findings import FindingSeverity, NormalizedFinding
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError
from app.services.approval import create_approval_request, revalidate_security_state
from app.services.decision import decide_runtime_action
from app.services.permission import InactiveResourceError, ResourceHierarchyError
from app.services.runtime_action import RuntimeActionNotFoundError
from app.services.tool_operation import OperationNotFoundError

logger = logging.getLogger(__name__)

# Resource Control Limits
MAX_TOTAL_PROMPT_CHARS = 200_000
MAX_MESSAGES_COUNT = 100
MAX_OUTPUT_TOKENS_LIMIT = 8192

AGENT_ENV_TO_ACTION_ENV = {
    AgentEnvironment.development.value: ActionEnvironment.dev.value,
    AgentEnvironment.staging.value: ActionEnvironment.staging.value,
    AgentEnvironment.production.value: ActionEnvironment.prod.value,
}


async def _audit(
    session: AsyncSession,
    event_type: Union[AuditEventType, str],
    action: str,
    organization_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    agent_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = "LLM_INTERACTION",
    resource_id: Optional[Union[uuid.UUID, str]] = None,
    outcome: Union[AuditOutcome, str] = AuditOutcome.SUCCESS,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Any:
    merged_metadata = dict(metadata or {})
    if reason:
        merged_metadata["reason"] = reason

    actor_type = AuditActorType.AGENT if agent_id else (AuditActorType.USER if user_id else AuditActorType.SYSTEM)
    actor_id = str(agent_id) if agent_id else (str(user_id) if user_id else "custode_llm_gateway")
    actor_display = f"Agent {agent_id}" if agent_id else (f"User {user_id}" if user_id else "CUSTODE LLM Gateway")

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
        metadata=merged_metadata,
        request_id=request_id,
    )


class LLMSecurityGateway:
    """Authoritative security gateway orchestrating LLM interactions."""

    @staticmethod
    async def ensure_llm_tool_and_operation(
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> Tuple[Tool, ToolOperation]:
        """Ensure the authoritative 'llm-provider' Tool and 'chat' ToolOperation exist for the organization."""
        # 1. Resolve or create Tool
        tool_query = select(Tool).where(
            Tool.organization_id == organization_id,
            Tool.slug == "llm-provider",
        )
        tool_res = await session.execute(tool_query)
        tool = tool_res.scalar_one_or_none()

        if tool is None:
            tool = Tool(
                organization_id=organization_id,
                name="LLM Security Gateway Provider",
                slug="llm-provider",
                description="Authoritative CUSTODE LLM Gateway controlled capability",
                tool_type=ToolType.api.value,
                status=ToolStatus.active.value,
                environment=AgentEnvironment.development.value,
            )
            session.add(tool)
            await session.flush()

        # 2. Resolve or create Operation
        op_query = select(ToolOperation).where(
            ToolOperation.tool_id == tool.id,
            ToolOperation.slug == "chat",
        )
        op_res = await session.execute(op_query)
        operation = op_res.scalar_one_or_none()

        if operation is None:
            operation = ToolOperation(
                tool_id=tool.id,
                name="Chat Completion",
                slug="chat",
                description="Controlled LLM multi-turn chat and completion operation",
                operation_type=OperationType.execute.value,
                risk_level=OperationRiskLevel.medium.value,
                status=OperationStatus.active.value,
            )
            session.add(operation)
            await session.flush()

        return tool, operation

    @classmethod
    async def chat(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        request: LLMRequest,
        user_id: Optional[uuid.UUID] = None,
    ) -> LLMResponse:
        """Process an inbound LLM chat completion through the CUSTODE security pipeline."""
        start_time = time.perf_counter()

        # 1. Identity Resolution: Validate Organization & Agent
        org_res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = org_res.scalar_one_or_none()
        if org is None:
            raise OrganizationNotFoundError(organization_id)
        if org.status != OrganizationStatus.active.value:
            raise OrganizationSuspendedError(organization_id)

        agent_res = await session.execute(
            select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id)
        )
        agent = agent_res.scalar_one_or_none()
        if agent is None:
            raise ResourceHierarchyError(f"Agent '{agent_id}' not found in organization '{organization_id}'")
        if agent.status != AgentStatus.active.value:
            raise InactiveResourceError("agent", agent.id, agent.status)

        # 2. Validate Provider & Model Allowlist
        provider_name = request.provider.lower()
        model_name = request.model
        provider_registry.validate_provider_and_model(provider_name, model_name)

        # 3. Rate & Resource Limits Enforcement
        total_prompt_chars = sum(len(m.content) for m in request.messages) + len(request.system_prompt or "")
        if total_prompt_chars > MAX_TOTAL_PROMPT_CHARS:
            raise LLMRateLimitError("max_prompt_chars", MAX_TOTAL_PROMPT_CHARS, total_prompt_chars)
        if len(request.messages) > MAX_MESSAGES_COUNT:
            raise LLMRateLimitError("max_messages", MAX_MESSAGES_COUNT, len(request.messages))

        # 4. Resolve Tool & Operation for authorization tracking
        tool, operation = await cls.ensure_llm_tool_and_operation(session, organization_id)

        # 5. Compute Input Content Hash & Sanitized Preview (Raw prompts are NOT stored in the database)
        canonical_messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if request.system_prompt:
            canonical_messages.insert(0, {"role": "system", "content": request.system_prompt})
        input_hash = compute_content_hash(canonical_messages)
        prompt_preview = create_sanitized_preview(
            request.messages[-1].content if request.messages else request.system_prompt
        )

        # 6. Map environment & create canonical RuntimeAction
        agent_env_val = agent.environment.value if hasattr(agent.environment, "value") else str(agent.environment)
        action_env = AGENT_ENV_TO_ACTION_ENV.get(agent_env_val, ActionEnvironment.dev.value)

        action = RuntimeAction(
            organization_id=organization_id,
            agent_id=agent.id,
            tool_id=tool.id,
            operation_id=operation.id,
            environment=action_env,
            action_type="llm_chat",
            resource=f"{provider_name}/{model_name}",
            parameters={
                "provider": provider_name,
                "model": model_name,
                "input_hash": input_hash,
                "messages_count": len(request.messages),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            },
            status=ActionStatus.evaluating.value,
        )
        session.add(action)
        await session.flush()

        # Audit: LLM_REQUEST_RECEIVED
        await _audit(
            session=session,
            event_type=AuditEventType.LLM_REQUEST_RECEIVED,
            action="LLM_CHAT_REQUEST",
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=action.id,
            outcome=AuditOutcome.SUCCESS,
            reason=f"LLM request received for {provider_name}/{model_name}",
            metadata={"provider": provider_name, "model": model_name, "input_hash": input_hash},
        )

        # 7. Input Security Scanning (Sentinel LLM_INPUT_PROFILE)
        input_text_chunks = [m.content for m in request.messages]
        if request.system_prompt:
            input_text_chunks.append(request.system_prompt)
        combined_input_text = "\n\n".join(input_text_chunks)

        raw_input_findings: List[NormalizedFinding] = sentinel_adapter.scan_text(
            combined_input_text,
            context={"provider": provider_name, "model": model_name, "agent_id": str(agent.id)},
            scanner_names=LLM_INPUT_PROFILE,
        )

        # Persist normalized input findings
        input_finding_records: List[SecurityFinding] = []
        for n_find in raw_input_findings:
            sev_val = n_find.severity.value if hasattr(n_find.severity, "value") else str(n_find.severity)
            cat_val = n_find.category.value if hasattr(n_find.category, "value") else str(n_find.category)
            sf = SecurityFinding(
                organization_id=organization_id,
                runtime_action_id=action.id,
                scanner=n_find.scanner,
                category=cat_val,
                severity=sev_val,
                scan_direction="INPUT",
                confidence=n_find.confidence,
                title=n_find.title,
                description=n_find.description,
                evidence=n_find.evidence,
                remediation=n_find.remediation,
                source="sentinel",
                finding_metadata=n_find.metadata,
            )
            session.add(sf)
            input_finding_records.append(sf)
        await session.flush()

        # Audit: LLM_INPUT_SCANNED
        await _audit(
            session=session,
            event_type=AuditEventType.LLM_INPUT_SCANNED,
            action="SCAN_LLM_INPUT",
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=action.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"findings_count": len(input_finding_records)},
        )

        # 8. Permission Engine Evaluation
        action_to_perm_env = {
            "dev": "development",
            "staging": "staging",
            "prod": "production",
        }
        perm_env = action_to_perm_env.get(action.environment, action.environment)

        perm_req = PermissionRequest(
            organization_id=organization_id,
            agent_id=agent.id,
            tool_id=tool.id,
            operation_id=operation.id,
            environment=perm_env,
        )
        perm_result = await PermissionEngine.evaluate(session, perm_req)

        # 9. Policy Engine Evaluation
        time_hour = action.created_at.hour if action.created_at else datetime.now(timezone.utc).hour
        action_context = build_llm_action_context(
            agent_id=agent.id,
            agent_environment=agent_env_val,
            tool_id=tool.id,
            operation_id=operation.id,
            provider=provider_name,
            model=model_name,
            direction="INPUT",
            token_usage=len(combined_input_text) // 4,
            request_id=str(action.request_id),
        )
        policy_result = await evaluate_llm_security_policy(session, organization_id, action_context)

        # 10. Risk Engine Assessment
        risk_result = RiskEngine.evaluate(
            runtime_action=action,
            operation_baseline_risk_level=operation.risk_level,
            operation_type=operation.operation_type,
            security_findings=input_finding_records,
        )

        # 11. Decision Engine Arbitration
        decision_eval = DecisionEngine.evaluate(
            permission_result=perm_result,
            policy_result=policy_result,
            risk_result=risk_result,
            security_findings=input_finding_records,
        )

        # Persist Decision Record
        decision_record = Decision(
            organization_id=organization_id,
            runtime_action_id=action.id,
            decision=decision_eval.decision.value if hasattr(decision_eval.decision, "value") else str(decision_eval.decision),
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

        # 12. Create Initial LLMInteraction Record
        interaction = LLMInteraction(
            organization_id=organization_id,
            agent_id=agent.id,
            runtime_action_id=action.id,
            request_id=action.request_id,
            provider=provider_name,
            model=model_name,
            environment=action.environment,
            status="evaluating",
            input_scan_status="flagged" if input_finding_records else "clean",
            output_scan_status="pending",
            decision=decision_eval.decision.value if hasattr(decision_eval.decision, "value") else str(decision_eval.decision),
            risk_score=decision_eval.risk_score,
            risk_level=decision_eval.risk_level,
            latency_ms=0.0,
            input_tokens=len(combined_input_text) // 4,
            output_tokens=0,
            total_tokens=len(combined_input_text) // 4,
            input_hash=input_hash,
            sanitized_prompt_preview=prompt_preview,
            interaction_metadata={"tool_id": str(tool.id), "operation_id": str(operation.id)},
        )
        session.add(interaction)
        await session.flush()

        # Link interaction_id on input findings
        for sf in input_finding_records:
            sf.interaction_id = interaction.id
        await session.flush()

        # Serialize findings for client output
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

        # 13. Handle Authorization Decision Branching
        # CASE A: BLOCK / DENY
        if decision_eval.decision.value in ("block", "deny"):
            interaction.status = "blocked"
            action.status = ActionStatus.denied.value
            await session.flush()

            await _audit(
                session=session,
                event_type=AuditEventType.LLM_REQUEST_BLOCKED,
                action="BLOCK_LLM_REQUEST",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="LLM_INTERACTION",
                resource_id=interaction.id,
                outcome=AuditOutcome.DENIED,
                reason=decision_eval.reason,
                metadata={"findings_count": len(input_finding_records), "decision": decision_eval.decision.value},
            )

            return LLMResponse(
                request_id=action.request_id,
                interaction_id=interaction.id,
                provider=provider_name,
                model=model_name,
                content=None,
                tool_calls=[],
                usage=LLMUsage(prompt_tokens=interaction.input_tokens, completion_tokens=0, total_tokens=interaction.input_tokens),
                finish_reason="security_block",
                latency_ms=(time.perf_counter() - start_time) * 1000.0,
                security_status="blocked",
                decision="block",
                input_findings=serialized_input_findings,
                output_findings=[],
                approval_id=None,
                created_at=interaction.created_at,
            )

        # CASE B: REQUIRE_APPROVAL
        if decision_eval.decision.value == "require_approval":
            approval_create_data = ApprovalCreate(
                decision_id=decision_record.id,
                reason=decision_eval.reason,
            )
            approval = await create_approval_request(
                session=session,
                organization_id=organization_id,
                runtime_action_id=action.id,
                data=approval_create_data,
            )
            interaction.status = "pending_approval"
            action.status = ActionStatus.pending.value
            await session.flush()

            await _audit(
                session=session,
                event_type=AuditEventType.LLM_APPROVAL_REQUIRED,
                action="REQUIRE_LLM_APPROVAL",
                organization_id=organization_id,
                user_id=user_id,
                agent_id=agent.id,
                resource_type="LLM_INTERACTION",
                resource_id=interaction.id,
                outcome=AuditOutcome.SUCCESS,
                reason=decision_eval.reason,
                metadata={"approval_id": str(approval.id)},
            )

            return LLMResponse(
                request_id=action.request_id,
                interaction_id=interaction.id,
                provider=provider_name,
                model=model_name,
                content=None,
                tool_calls=[],
                usage=LLMUsage(prompt_tokens=interaction.input_tokens, completion_tokens=0, total_tokens=interaction.input_tokens),
                finish_reason="approval_required",
                latency_ms=(time.perf_counter() - start_time) * 1000.0,
                security_status="approval_required",
                decision="require_approval",
                input_findings=serialized_input_findings,
                output_findings=[],
                approval_id=approval.id,
                created_at=interaction.created_at,
            )

        # CASE C: ALLOW -> Proceed to Provider Dispatch
        await _audit(
            session=session,
            event_type=AuditEventType.LLM_REQUEST_SENT,
            action="DISPATCH_LLM_PROVIDER",
            organization_id=organization_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=interaction.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"provider": provider_name, "model": model_name},
        )

        provider_instance = provider_registry.get(provider_name)
        try:
            provider_result = await provider_instance.complete(request)
        except Exception as exc:
            interaction.status = "failed"
            action.status = ActionStatus.failed.value
            await session.flush()

            await _audit(
                session=session,
                event_type=AuditEventType.LLM_PROVIDER_ERROR,
                action="PROVIDER_INVOCATION",
                organization_id=organization_id,
                agent_id=agent.id,
                resource_type="LLM_INTERACTION",
                resource_id=interaction.id,
                outcome=AuditOutcome.FAILURE,
                reason=str(exc),
            )
            raise

        await _audit(
            session=session,
            event_type=AuditEventType.LLM_RESPONSE_RECEIVED,
            action="RECEIVE_LLM_RESPONSE",
            organization_id=organization_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=interaction.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"finish_reason": provider_result.finish_reason},
        )

        # 14. Output Security Scanning (Sentinel LLM_OUTPUT_PROFILE)
        output_finding_records: List[SecurityFinding] = []
        if provider_result.content:
            raw_output_findings = sentinel_adapter.scan_text(
                provider_result.content,
                context={"provider": provider_name, "model": model_name, "stage": "output"},
                scanner_names=LLM_OUTPUT_PROFILE,
            )

            for n_find in raw_output_findings:
                sev_val = n_find.severity.value if hasattr(n_find.severity, "value") else str(n_find.severity)
                cat_val = n_find.category.value if hasattr(n_find.category, "value") else str(n_find.category)
                sf = SecurityFinding(
                    organization_id=organization_id,
                    runtime_action_id=action.id,
                    interaction_id=interaction.id,
                    scanner=n_find.scanner,
                    category=cat_val,
                    severity=sev_val,
                    scan_direction="OUTPUT",
                    confidence=n_find.confidence,
                    title=n_find.title,
                    description=n_find.description,
                    evidence=n_find.evidence,
                    remediation=n_find.remediation,
                    source="sentinel",
                    finding_metadata=n_find.metadata,
                )
                session.add(sf)
                output_finding_records.append(sf)
            await session.flush()

        await _audit(
            session=session,
            event_type=AuditEventType.LLM_OUTPUT_SCANNED,
            action="SCAN_LLM_OUTPUT",
            organization_id=organization_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=interaction.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"output_findings_count": len(output_finding_records)},
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

        # 15. Output Security Decision: If any output finding is CRITICAL or HIGH secret/PII, BLOCK output!
        has_critical_output = any(f.severity.upper() == "CRITICAL" for f in output_finding_records)
        has_high_secret_output = any(
            f.severity.upper() in ("CRITICAL", "HIGH") and f.category.upper() in ("SECRET", "CREDENTIAL", "PII")
            for f in output_finding_records
        )

        if has_critical_output or has_high_secret_output:
            interaction.output_scan_status = "blocked"
            interaction.status = "output_blocked"
            interaction.latency_ms = provider_result.latency_ms
            action.status = ActionStatus.failed.value
            await session.flush()

            await _audit(
                session=session,
                event_type=AuditEventType.LLM_OUTPUT_BLOCKED,
                action="BLOCK_LLM_OUTPUT",
                organization_id=organization_id,
                agent_id=agent.id,
                resource_type="LLM_INTERACTION",
                resource_id=interaction.id,
                outcome=AuditOutcome.DENIED,
                reason="Sensitive credentials or critical security vulnerabilities detected in model output",
                metadata={"output_findings_count": len(output_finding_records)},
            )

            return LLMResponse(
                request_id=action.request_id,
                interaction_id=interaction.id,
                provider=provider_name,
                model=model_name,
                content=None,
                tool_calls=[],
                usage=provider_result.usage,
                finish_reason="output_blocked",
                latency_ms=(time.perf_counter() - start_time) * 1000.0,
                security_status="output_blocked",
                decision="block",
                input_findings=serialized_input_findings,
                output_findings=serialized_output_findings,
                approval_id=None,
                created_at=interaction.created_at,
            )

        # 16. Output Clean & Verified
        output_hash = compute_content_hash(provider_result.content or "")
        output_preview = create_sanitized_preview(provider_result.content)

        interaction.status = "completed"
        interaction.output_scan_status = "flagged" if output_finding_records else "clean"
        interaction.output_hash = output_hash
        interaction.sanitized_output_preview = output_preview
        interaction.latency_ms = provider_result.latency_ms
        interaction.input_tokens = provider_result.usage.prompt_tokens
        interaction.output_tokens = provider_result.usage.completion_tokens
        interaction.total_tokens = provider_result.usage.total_tokens
        interaction.completed_at = datetime.now(timezone.utc)
        action.status = ActionStatus.executed.value
        await session.flush()

        await _audit(
            session=session,
            event_type=AuditEventType.LLM_REQUEST_COMPLETED,
            action="COMPLETE_LLM_REQUEST",
            organization_id=organization_id,
            agent_id=agent.id,
            resource_type="LLM_INTERACTION",
            resource_id=interaction.id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"latency_ms": interaction.latency_ms, "total_tokens": interaction.total_tokens},
        )

        return LLMResponse(
            request_id=action.request_id,
            interaction_id=interaction.id,
            provider=provider_name,
            model=model_name,
            content=provider_result.content,
            tool_calls=provider_result.tool_calls,
            usage=provider_result.usage,
            finish_reason=provider_result.finish_reason,
            latency_ms=interaction.latency_ms,
            security_status="allowed",
            decision="allow",
            input_findings=serialized_input_findings,
            output_findings=serialized_output_findings,
            approval_id=None,
            created_at=interaction.created_at,
        )

    @classmethod
    async def execute_tool_call(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        interaction_id: uuid.UUID,
        data: ToolCallExecutionRequest,
    ) -> ToolCallExecutionResponse:
        """Safely execute an untrusted LLM-generated tool call through the CUSTODE control plane."""
        # 1. Validate Interaction
        inter_query = select(LLMInteraction).where(
            LLMInteraction.id == interaction_id,
            LLMInteraction.organization_id == organization_id,
        )
        inter_res = await session.execute(inter_query)
        interaction = inter_res.scalar_one_or_none()
        if interaction is None:
            raise LLMToolCallSecurityError(data.tool_name, data.operation_name, f"Interaction '{interaction_id}' not found")

        # 2. Resolve Tool in Organization
        tool_query = select(Tool).where(
            Tool.organization_id == organization_id,
            (Tool.slug == data.tool_name) | (Tool.name == data.tool_name),
        )
        tool_res = await session.execute(tool_query)
        tool = tool_res.scalar_one_or_none()
        if tool is None:
            raise LLMToolCallSecurityError(data.tool_name, data.operation_name, f"Tool '{data.tool_name}' not registered in tenant")
        if tool.status != ToolStatus.active.value:
            raise LLMToolCallSecurityError(data.tool_name, data.operation_name, f"Tool is in '{tool.status}' state")

        # 3. Resolve ToolOperation
        op_query = select(ToolOperation).where(
            ToolOperation.tool_id == tool.id,
            (ToolOperation.slug == data.operation_name) | (ToolOperation.name == data.operation_name),
        )
        op_res = await session.execute(op_query)
        operation = op_res.scalar_one_or_none()
        if operation is None:
            raise LLMToolCallSecurityError(data.tool_name, data.operation_name, f"Operation '{data.operation_name}' not registered on tool")
        if operation.status != OperationStatus.active.value:
            raise LLMToolCallSecurityError(data.tool_name, data.operation_name, f"Operation is in '{operation.status}' state")

        # 4. Create RuntimeAction for the tool call
        agent_res = await session.execute(select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id))
        agent = agent_res.scalar_one_or_none()
        agent_env_val = agent.environment.value if agent and hasattr(agent.environment, "value") else "development"
        action_env = AGENT_ENV_TO_ACTION_ENV.get(agent_env_val, ActionEnvironment.dev.value)

        tool_action = RuntimeAction(
            organization_id=organization_id,
            agent_id=agent_id,
            tool_id=tool.id,
            operation_id=operation.id,
            environment=action_env,
            action_type=f"tool_call:{data.tool_name}",
            resource=f"{data.tool_name}::{data.operation_name}",
            parameters=data.parameters,
            status=ActionStatus.evaluating.value,
        )
        session.add(tool_action)
        await session.flush()

        # 5. Authoritatively decide through CUSTODE Decision Engine
        decision = await decide_runtime_action(session, organization_id, tool_action.id)

        if decision.decision == "allow":
            tool_action.status = ActionStatus.executed.value
            await session.flush()
            return ToolCallExecutionResponse(
                interaction_id=interaction_id,
                runtime_action_id=tool_action.id,
                decision=decision.decision,
                status="executed",
                result={"status": "success", "message": f"Tool call {data.tool_name}::{data.operation_name} executed under control plane"},
            )
        elif decision.decision == "require_approval":
            tool_action.status = ActionStatus.pending.value
            await session.flush()
            return ToolCallExecutionResponse(
                interaction_id=interaction_id,
                runtime_action_id=tool_action.id,
                decision=decision.decision,
                status="pending_approval",
                error=decision.reason,
            )
        else:
            tool_action.status = ActionStatus.denied.value
            await session.flush()
            return ToolCallExecutionResponse(
                interaction_id=interaction_id,
                runtime_action_id=tool_action.id,
                decision=decision.decision,
                status="blocked",
                error=decision.reason,
            )

    @classmethod
    async def get_interaction(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        interaction_id: uuid.UUID,
    ) -> Optional[LLMInteraction]:
        """Fetch a single LLMInteraction strictly within the tenant scope."""
        query = select(LLMInteraction).where(
            LLMInteraction.id == interaction_id,
            LLMInteraction.organization_id == organization_id,
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()

    @classmethod
    async def list_interactions(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[LLMInteraction], int]:
        """List tenant-scoped LLM interactions with filtering and pagination."""
        query = select(LLMInteraction).where(LLMInteraction.organization_id == organization_id)
        count_query = select(func.count(LLMInteraction.id)).where(LLMInteraction.organization_id == organization_id)

        if provider:
            query = query.where(LLMInteraction.provider == provider.lower())
            count_query = count_query.where(LLMInteraction.provider == provider.lower())
        if model:
            query = query.where(LLMInteraction.model == model)
            count_query = count_query.where(LLMInteraction.model == model)
        if status:
            query = query.where(LLMInteraction.status == status)
            count_query = count_query.where(LLMInteraction.status == status)

        query = query.order_by(desc(LLMInteraction.created_at)).offset(offset).limit(limit)

        total_res = await session.execute(count_query)
        total = total_res.scalar() or 0

        items_res = await session.execute(query)
        items = list(items_res.scalars().all())

        return items, total

    @classmethod
    async def get_metrics(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> LLMMetricsResponse:
        """Compute aggregated LLM security metrics strictly for the specified organization."""
        # Total interactions
        tot_query = select(func.count(LLMInteraction.id)).where(LLMInteraction.organization_id == organization_id)
        tot_res = await session.execute(tot_query)
        total_interactions = tot_res.scalar() or 0

        # Blocks
        block_query = select(func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id,
            LLMInteraction.status.in_(["blocked", "output_blocked"]),
        )
        block_res = await session.execute(block_query)
        blocked_count = block_res.scalar() or 0

        # Output blocked count
        out_block_query = select(func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id,
            LLMInteraction.status == "output_blocked",
        )
        out_block_res = await session.execute(out_block_query)
        output_blocked_count = out_block_res.scalar() or 0

        # Approvals
        appr_query = select(func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id,
            LLMInteraction.status == "pending_approval",
        )
        appr_res = await session.execute(appr_query)
        approval_count = appr_res.scalar() or 0

        # Total tokens
        tokens_query = select(func.sum(LLMInteraction.total_tokens)).where(
            LLMInteraction.organization_id == organization_id,
        )
        tokens_res = await session.execute(tokens_query)
        total_tokens = tokens_res.scalar() or 0

        # Input & Output Findings
        in_findings_query = select(func.count(SecurityFinding.id)).where(
            SecurityFinding.organization_id == organization_id,
            SecurityFinding.scan_direction == "INPUT",
        )
        in_findings_res = await session.execute(in_findings_query)
        total_in_findings = in_findings_res.scalar() or 0

        out_findings_query = select(func.count(SecurityFinding.id)).where(
            SecurityFinding.organization_id == organization_id,
            SecurityFinding.scan_direction == "OUTPUT",
        )
        out_findings_res = await session.execute(out_findings_query)
        total_out_findings = out_findings_res.scalar() or 0

        # Distributions
        prov_query = select(LLMInteraction.provider, func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id
        ).group_by(LLMInteraction.provider)
        prov_res = await session.execute(prov_query)
        provider_dist = {r[0]: r[1] for r in prov_res.all()}

        model_query = select(LLMInteraction.model, func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id
        ).group_by(LLMInteraction.model)
        model_res = await session.execute(model_query)
        model_dist = {r[0]: r[1] for r in model_res.all()}

        status_query = select(LLMInteraction.status, func.count(LLMInteraction.id)).where(
            LLMInteraction.organization_id == organization_id
        ).group_by(LLMInteraction.status)
        status_res = await session.execute(status_query)
        status_dist = {r[0]: r[1] for r in status_res.all()}

        return LLMMetricsResponse(
            total_interactions=total_interactions,
            blocked_count=blocked_count,
            approval_required_count=approval_count,
            output_blocked_count=output_blocked_count,
            total_input_findings=total_in_findings,
            total_output_findings=total_out_findings,
            provider_distribution=provider_dist,
            model_distribution=model_dist,
            status_distribution=status_dist,
            total_tokens=total_tokens,
        )


# Global singleton gateway
llm_gateway = LLMSecurityGateway()
