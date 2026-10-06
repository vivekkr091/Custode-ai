"""Automated tests for RuntimeAction model, normalization, validation, lifecycle, and tenant isolation."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.runtime_action import ActionStatus
from app.runtime.normalizer import (
    ActionNormalizer,
    NormalizationError,
    normalize_action_type,
    normalize_amount,
    normalize_currency,
    normalize_environment,
    normalize_ip_address,
    normalize_parameters,
    normalize_request_id,
    normalize_resource,
    normalize_resource_type,
)
from app.schemas.runtime_action import RuntimeActionCreate


async def setup_hierarchy(
    async_client: AsyncClient,
    org_name: str = "Runtime Org",
    agent_env: str = "development",
):
    """Helper to provision Org, User, Agent, Tool, and Operation."""
    # 1. Org
    org = (await async_client.post("/api/v1/organizations", json={"name": org_name})).json()
    org_id = org["id"]

    # 2. Agent
    agent = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents",
            json={"name": f"{org_name} Agent", "environment": agent_env},
        )
    ).json()
    agent_id = agent["id"]

    # 3. Agent Credential
    cred = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/agents/{agent_id}/credentials",
            json={"name": "API Key"},
        )
    ).json()
    raw_api_key = cred["api_key"]

    # 4. Tool
    tool = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools",
            json={"name": f"{org_name} Tool"},
        )
    ).json()
    tool_id = tool["id"]

    # 5. Operation
    operation = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations",
            json={"name": "Execute Query", "operation_type": "read"},
        )
    ).json()
    operation_id = operation["id"]

    return org_id, agent_id, raw_api_key, tool_id, operation_id


@pytest.mark.asyncio
async def test_runtime_action_creation_success(async_client: AsyncClient) -> None:
    """A. Valid action creation succeeds with both Bearer token and X-Agent-ID."""
    org_id, agent_id, raw_key, tool_id, op_id = await setup_hierarchy(async_client, "Creation Org")

    payload = {
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "dev",
        "action_type": "query",
        "resource": "/api/v1/records/",
        "resource_type": "table",
        "parameters": {"limit": 10, "filter": "active"},
        "amount": 49.99,
        "currency": "usd",
        "ip_address": "192.168.1.1",
        "user_agent": "AgentWorker/1.0",
    }

    # 1. Via Authorization Bearer
    res = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=payload,
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["organization_id"] == org_id
    assert data["agent_id"] == agent_id
    assert data["tool_id"] == tool_id
    assert data["operation_id"] == op_id
    assert data["environment"] == "dev"
    assert data["action_type"] == "query"
    assert data["resource"] == "/api/v1/records"  # normalized stripped trailing slash
    assert data["resource_type"] == "table"
    assert data["parameters"] == {"limit": 10, "filter": "active"}
    assert data["amount"] == 49.99
    assert data["currency"] == "USD"
    assert data["status"] == "pending"
    assert data["request_id"] is not None
    assert data["evaluated_at"] is None
    assert data["completed_at"] is None

    # 2. Via X-Agent-ID header
    res2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=payload,
        headers={"X-Agent-ID": agent_id},
    )
    assert res2.status_code == 201
    assert res2.json()["agent_id"] == agent_id


@pytest.mark.asyncio
async def test_runtime_action_missing_or_inactive_org(async_client: AsyncClient) -> None:
    """B & C: Rejects missing organization or inactive organization."""
    org_id, agent_id, _, tool_id, op_id = await setup_hierarchy(async_client, "Org Status Org")
    fake_org_id = str(uuid.uuid4())

    payload = {
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "dev",
        "action_type": "read",
    }

    # B. Missing org
    res_missing = await async_client.post(
        f"/api/v1/organizations/{fake_org_id}/runtime-actions",
        json=payload,
        headers={"X-Agent-ID": agent_id},
    )
    assert res_missing.status_code == 404

    # C. Inactive org (suspend organization directly in DB or test hierarchy)
    # Using org with non-existent or suspended status
    from tests.conftest import TestingSessionLocal
    from app.db.models.organization import Organization, OrganizationStatus
    from sqlalchemy import select

    async with TestingSessionLocal() as session:
        org_obj = (await session.execute(select(Organization).where(Organization.id == uuid.UUID(org_id)))).scalar_one()
        org_obj.status = OrganizationStatus.suspended.value
        session.add(org_obj)
        await session.commit()

    res_suspended = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=payload,
        headers={"X-Agent-ID": agent_id},
    )
    assert res_suspended.status_code == 409


@pytest.mark.asyncio
async def test_runtime_action_agent_validations(async_client: AsyncClient) -> None:
    """D & E: Rejects agent not in org or inactive agent."""
    org_a_id, agent_a_id, _, tool_a_id, op_a_id = await setup_hierarchy(async_client, "Agent Org A")
    org_b_id, agent_b_id, _, _, _ = await setup_hierarchy(async_client, "Agent Org B")

    payload = {
        "tool_id": tool_a_id,
        "operation_id": op_a_id,
        "environment": "dev",
        "action_type": "fetch",
    }

    # D. Agent B not in Org A
    res_cross = await async_client.post(
        f"/api/v1/organizations/{org_a_id}/runtime-actions",
        json=payload,
        headers={"X-Agent-ID": agent_b_id},
    )
    assert res_cross.status_code == 404

    # E. Inactive (suspended) agent
    await async_client.post(f"/api/v1/organizations/{org_a_id}/agents/{agent_a_id}/suspend")
    res_inactive = await async_client.post(
        f"/api/v1/organizations/{org_a_id}/runtime-actions",
        json=payload,
        headers={"X-Agent-ID": agent_a_id},
    )
    assert res_inactive.status_code == 409


@pytest.mark.asyncio
async def test_runtime_action_tool_and_operation_validations(async_client: AsyncClient) -> None:
    """F, G, H, I: Validates tool in org, active tool, operation on tool, and active operation."""
    org_id, agent_id, _, tool_id, op_id = await setup_hierarchy(async_client, "Tool Validations Org")
    fake_id = str(uuid.uuid4())

    base_payload = {
        "tool_id": tool_id,
        "operation_id": op_id,
        "environment": "dev",
        "action_type": "execute",
    }

    # F. Tool not in organization
    p_fake_tool = {**base_payload, "tool_id": fake_id}
    res_tool_not_found = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=p_fake_tool,
        headers={"X-Agent-ID": agent_id},
    )
    assert res_tool_not_found.status_code == 404

    # G. Inactive tool (create a dedicated tool and suspend it)
    tool_susp = (
        await async_client.post(
            f"/api/v1/organizations/{org_id}/tools",
            json={"name": "Suspended Tool"},
        )
    ).json()
    susp_tool_id = tool_susp["id"]
    await async_client.post(f"/api/v1/organizations/{org_id}/tools/{susp_tool_id}/suspend")

    res_tool_suspended = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={**base_payload, "tool_id": susp_tool_id},
        headers={"X-Agent-ID": agent_id},
    )
    assert res_tool_suspended.status_code == 409

    # H. Operation not attached to tool
    p_fake_op = {**base_payload, "operation_id": fake_id}
    res_op_not_found = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=p_fake_op,
        headers={"X-Agent-ID": agent_id},
    )
    assert res_op_not_found.status_code == 404

    # I. Inactive operation
    await async_client.post(f"/api/v1/organizations/{org_id}/tools/{tool_id}/operations/{op_id}/suspend")
    res_op_suspended = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json=base_payload,
        headers={"X-Agent-ID": agent_id},
    )
    assert res_op_suspended.status_code == 409


@pytest.mark.asyncio
async def test_environment_validations_and_agent_compatibility(async_client: AsyncClient) -> None:
    """J. Invalid environment rejection and agent environment compatibility enforcement."""
    org_id, dev_agent_id, _, tool_id, op_id = await setup_hierarchy(
        async_client, "Env Compatibility Org", agent_env="development"
    )

    # 1. Invalid environment string
    res_invalid_env = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "super-prod-9000",
            "action_type": "write",
        },
        headers={"X-Agent-ID": dev_agent_id},
    )
    assert res_invalid_env.status_code == 422

    # 2. Incompatible environment: dev agent attempting action in prod
    res_incompatible = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "prod",
            "action_type": "write",
        },
        headers={"X-Agent-ID": dev_agent_id},
    )
    assert res_incompatible.status_code == 409


@pytest.mark.asyncio
async def test_lifecycle_transitions_valid_and_invalid(async_client: AsyncClient) -> None:
    """K & L: Valid lifecycle transitions succeed and illegal transitions are rejected."""
    org_id, agent_id, _, tool_id, op_id = await setup_hierarchy(async_client, "Transitions Org")

    create_res = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "dev",
            "action_type": "transfer",
        },
        headers={"X-Agent-ID": agent_id},
    )
    action_id = create_res.json()["id"]

    # 1. Valid: pending -> evaluating
    t1 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/transition",
        json={"target_status": "evaluating"},
    )
    assert t1.status_code == 200
    assert t1.json()["status"] == "evaluating"
    assert t1.json()["evaluated_at"] is not None

    # 2. Invalid: evaluating -> executed (illegal jump)
    t_invalid = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/transition",
        json={"target_status": "executed"},
    )
    assert t_invalid.status_code == 409

    # 3. Valid: evaluating -> approved
    t2 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/transition",
        json={"target_status": "approved"},
    )
    assert t2.status_code == 200
    assert t2.json()["status"] == "approved"

    # 4. Valid: approved -> executed
    t3 = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/transition",
        json={"target_status": "executed"},
    )
    assert t3.status_code == 200
    assert t3.json()["status"] == "executed"
    assert t3.json()["completed_at"] is not None

    # 5. Invalid: executed -> pending (terminal state cannot revert)
    t_terminal = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions/{action_id}/transition",
        json={"target_status": "pending"},
    )
    assert t_terminal.status_code == 409


@pytest.mark.asyncio
async def test_tenant_isolation_for_runtime_actions(async_client: AsyncClient) -> None:
    """M. Strict tenant isolation: Org B cannot access or transition Org A's action."""
    org_a, agent_a, _, tool_a, op_a = await setup_hierarchy(async_client, "Isolation Org A")
    org_b, _, _, _, _ = await setup_hierarchy(async_client, "Isolation Org B")

    # Create action in Org A
    action_a = (
        await async_client.post(
            f"/api/v1/organizations/{org_a}/runtime-actions",
            json={
                "tool_id": tool_a,
                "operation_id": op_a,
                "environment": "dev",
                "action_type": "scan",
            },
            headers={"X-Agent-ID": agent_a},
        )
    ).json()
    action_id = action_a["id"]

    # 1. Org B cannot retrieve action
    res_get = await async_client.get(
        f"/api/v1/organizations/{org_b}/runtime-actions/{action_id}"
    )
    assert res_get.status_code == 404

    # 2. Org B cannot transition action
    res_trans = await async_client.post(
        f"/api/v1/organizations/{org_b}/runtime-actions/{action_id}/transition",
        json={"target_status": "evaluating"},
    )
    assert res_trans.status_code == 404

    # 3. Org B listing does not include Org A's action
    res_list = await async_client.get(
        f"/api/v1/organizations/{org_b}/runtime-actions"
    )
    assert res_list.status_code == 200
    assert len(res_list.json()["items"]) == 0


def test_normalization_and_parameter_handling() -> None:
    """N, O, P: Validates normalization, parameter serialization, and request_id handling."""
    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    op_id = uuid.uuid4()
    custom_req_id = uuid.uuid4()

    # Normalization tests
    assert normalize_environment("DEV") == "dev"
    assert normalize_environment("development ") == "dev"
    assert normalize_environment("Prod") == "prod"
    assert normalize_action_type("  Read_Database ") == "read_database"
    assert normalize_resource(" /api/v1/users/// ") == "/api/v1/users"
    assert normalize_resource("/") == "/"
    assert normalize_resource_type("  Database_Table  ") == "database_table"
    assert normalize_amount("123.456789") == 123.4568
    assert normalize_currency("usd ") == "USD"
    assert normalize_ip_address("  10.0.0.1  ") == "10.0.0.1"

    with pytest.raises(NormalizationError):
        normalize_amount(-10)

    with pytest.raises(NormalizationError):
        normalize_ip_address("999.999.999.999")

    # ActionNormalizer canonical output
    req = RuntimeActionCreate(
        tool_id=tool_id,
        operation_id=op_id,
        environment="development",
        action_type=" EXECUTE_SQL ",
        resource="db://finance/transactions/",
        resource_type="TABLE",
        parameters={"table": "tx", "nested": {"count": 5}},
        amount=150.25,
        currency="usd",
        ip_address="127.0.0.1",
        user_agent="Worker",
        request_id=custom_req_id,
    )

    canonical = ActionNormalizer.normalize(
        organization_id=org_id,
        agent_id=agent_id,
        data=req,
    )

    assert canonical.organization_id == org_id
    assert canonical.agent_id == agent_id
    assert canonical.request_id == custom_req_id
    assert canonical.environment == "dev"
    assert canonical.action_type == "execute_sql"
    assert canonical.resource == "db://finance/transactions"
    assert canonical.resource_type == "table"
    assert canonical.parameters == {"table": "tx", "nested": {"count": 5}}
    assert canonical.currency == "USD"


@pytest.mark.asyncio
async def test_api_validation_errors(async_client: AsyncClient) -> None:
    """Q. API validation rejects client-injected control fields and missing identity."""
    org_id, _, _, tool_id, op_id = await setup_hierarchy(async_client, "API Validation Org")

    # Missing agent header
    res_no_auth = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "dev",
            "action_type": "write",
        },
    )
    assert res_no_auth.status_code == 401

    # Client attempting to inject organization_id or agent_id directly into payload
    res_forbidden_field = await async_client.post(
        f"/api/v1/organizations/{org_id}/runtime-actions",
        json={
            "tool_id": tool_id,
            "operation_id": op_id,
            "environment": "dev",
            "action_type": "write",
            "organization_id": str(uuid.uuid4()),
        },
        headers={"X-Agent-ID": str(uuid.uuid4())},
    )
    assert res_forbidden_field.status_code == 422
