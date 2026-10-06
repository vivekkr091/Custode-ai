"""RBAC Role Boundary and Privilege Escalation Red Team Tests (Milestone 22)."""

import uuid
import pytest
from httpx import AsyncClient

from app.db.models.membership import MembershipRole
from app.services.integrations.ssrf import set_custom_dns_resolver


@pytest.fixture(autouse=True)
def mock_dns():
    def _mock_resolver(host: str, port: int):
        return ["93.184.216.34"]
    set_custom_dns_resolver(_mock_resolver)
    yield
    set_custom_dns_resolver(None)


async def _setup_rbac_fixture(async_client: AsyncClient):
    """Create an organization and four users with distinct roles."""
    org_resp = await async_client.post("/api/v1/organizations", json={"name": f"RBAC Org {uuid.uuid4().hex[:6]}"})
    org_id = org_resp.json()["id"]

    roles = [
        MembershipRole.organization_admin.value,
        MembershipRole.security_analyst.value,
        MembershipRole.developer.value,
        MembershipRole.viewer.value,
    ]
    users = {}

    for r in roles:
        u_resp = await async_client.post(
            "/api/v1/users",
            json={"email": f"{r}_{uuid.uuid4().hex[:6]}@custode.io", "display_name": f"User {r}"},
        )
        uid = u_resp.json()["id"]
        await async_client.post(
            f"/api/v1/organizations/{org_id}/memberships",
            json={"user_id": uid, "role": r},
        )
        users[r] = uid

    return org_id, users


@pytest.mark.asyncio
async def test_rbac_integration_management_restricted_to_admin(async_client: AsyncClient):
    """Verify that only organization_admin can create, suspend, or revoke integrations."""
    org_id, users = await _setup_rbac_fixture(async_client)

    # 1. Viewer attempts to create integration -> 403
    viewer_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/integrations",
        json={"name": "Viewer Webhook", "url": "https://example.com/alerts", "subscribed_events": ["DECISION_CREATED"]},
        headers={"X-User-ID": users[MembershipRole.viewer.value]},
    )
    assert viewer_resp.status_code == 403

    # 2. Developer attempts to create integration -> 403
    dev_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/integrations",
        json={"name": "Dev Webhook", "url": "https://example.com/alerts", "subscribed_events": ["DECISION_CREATED"]},
        headers={"X-User-ID": users[MembershipRole.developer.value]},
    )
    assert dev_resp.status_code == 403

    # 3. Security Analyst attempts to create integration -> 403 (requires admin)
    analyst_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/integrations",
        json={"name": "Analyst Webhook", "url": "https://example.com/alerts", "subscribed_events": ["DECISION_CREATED"]},
        headers={"X-User-ID": users[MembershipRole.security_analyst.value]},
    )
    assert analyst_resp.status_code == 403

    # 4. Admin succeeds -> 201
    admin_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/integrations",
        json={"name": "Admin Webhook", "url": "https://example.com/alerts", "subscribed_events": ["DECISION_CREATED"]},
        headers={"X-User-ID": users[MembershipRole.organization_admin.value]},
    )
    assert admin_resp.status_code == 201


@pytest.mark.asyncio
async def test_rbac_read_operations_permitted_for_all_active_members(async_client: AsyncClient):
    """Verify that viewer, developer, analyst, and admin can all list integrations."""
    org_id, users = await _setup_rbac_fixture(async_client)

    for role_name, user_id in users.items():
        resp = await async_client.get(
            f"/api/v1/organizations/{org_id}/integrations",
            headers={"X-User-ID": user_id},
        )
        assert resp.status_code == 200, f"Role {role_name} failed to list integrations: {resp.text}"
