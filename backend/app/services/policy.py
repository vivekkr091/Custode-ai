"""Service layer for Policy management, Policy Versioning, and Policy Engine evaluation coordination."""

from datetime import datetime, timezone
import re
from typing import List, Optional, Union
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization, OrganizationStatus
from app.db.models.policy import EnforcementMode, Policy, PolicyStatus
from app.db.models.policy_version import PolicyVersion, PolicyVersionStatus
from app.engines.policy.evaluator import PolicyEngine
from app.schemas.policy import (
    ActionContext,
    PolicyCreate,
    PolicyEvaluationResult,
    PolicyRule,
    PolicyUpdate,
    PolicyVersionCreate,
)
from app.services.agent import OrganizationNotFoundError, OrganizationSuspendedError


class PolicyNotFoundError(Exception):
    """Raised when a policy cannot be found within an organization."""
    def __init__(self, org_id: uuid.UUID, policy_identifier: Union[uuid.UUID, str]):
        super().__init__(f"Policy '{policy_identifier}' not found in organization '{org_id}'")
        self.org_id = org_id
        self.policy_identifier = policy_identifier


class PolicyVersionNotFoundError(Exception):
    """Raised when a policy version cannot be found."""
    def __init__(self, policy_id: uuid.UUID, version_identifier: Union[uuid.UUID, int]):
        super().__init__(f"Policy version '{version_identifier}' not found for policy '{policy_id}'")
        self.policy_id = policy_id
        self.version_identifier = version_identifier


class DuplicatePolicySlugError(Exception):
    """Raised when a policy with the specified slug already exists in the organization."""
    def __init__(self, org_id: uuid.UUID, slug: str):
        super().__init__(f"Policy with slug '{slug}' already exists in organization '{org_id}'")
        self.org_id = org_id
        self.slug = slug


class PolicyVersionImmutableError(Exception):
    """Raised when an edit is attempted on a published or retired policy version."""
    def __init__(self, version_id: uuid.UUID, status: str):
        super().__init__(f"Policy version '{version_id}' is immutable in status '{status}'")
        self.version_id = version_id
        self.status = status


def _slugify(name: str) -> str:
    """Generate a clean URL-friendly slug from name."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    clean = re.sub(r"[-\s]+", "-", clean)
    return clean or "policy"


async def get_active_policy_version_number(
    session: AsyncSession, policy_id: uuid.UUID
) -> Optional[int]:
    """Helper to get currently published version number for a policy."""
    query = select(PolicyVersion.version).where(
        PolicyVersion.policy_id == policy_id,
        PolicyVersion.status == PolicyVersionStatus.published.value,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def create_policy(
    session: AsyncSession, organization_id: uuid.UUID, data: PolicyCreate
) -> Policy:
    """Create a new policy container within an organization."""
    # 1. Validate Organization
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    slug = data.slug or _slugify(data.name)

    # 2. Check slug uniqueness
    dup_res = await session.execute(
        select(Policy).where(
            Policy.organization_id == organization_id,
            Policy.slug == slug,
        )
    )
    if dup_res.scalar_one_or_none() is not None:
        raise DuplicatePolicySlugError(organization_id, slug)

    policy = Policy(
        organization_id=organization_id,
        name=data.name,
        slug=slug,
        description=data.description,
        status=PolicyStatus.draft.value,
        enforcement_mode=data.enforcement_mode.value,
    )
    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    return policy


async def get_policy(
    session: AsyncSession, organization_id: uuid.UUID, policy_id: uuid.UUID
) -> Optional[Policy]:
    """Retrieve a single policy scoped to an organization."""
    query = select(Policy).where(
        Policy.organization_id == organization_id,
        Policy.id == policy_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_policies(
    session: AsyncSession,
    organization_id: uuid.UUID,
    status: Optional[str] = None,
    enforcement_mode: Optional[str] = None,
) -> List[Policy]:
    """List policies scoped to an organization with optional filters."""
    query = select(Policy).where(Policy.organization_id == organization_id)
    if status:
        query = query.where(Policy.status == status)
    if enforcement_mode:
        query = query.where(Policy.enforcement_mode == enforcement_mode)
    query = query.order_by(Policy.created_at.desc())
    res = await session.execute(query)
    return list(res.scalars().all())


async def update_policy(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    data: PolicyUpdate,
) -> Policy:
    """Update policy attributes (name, description, status, enforcement_mode)."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(organization_id, policy_id)

    if data.name is not None:
        policy.name = data.name
    if data.description is not None:
        policy.description = data.description
    if data.status is not None:
        policy.status = data.status.value
    if data.enforcement_mode is not None:
        policy.enforcement_mode = data.enforcement_mode.value

    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    return policy


async def create_policy_version(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    data: PolicyVersionCreate,
) -> PolicyVersion:
    """Draft a new policy version with sequential version numbering."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(organization_id, policy_id)

    # Determine next version number
    max_ver_res = await session.execute(
        select(func.max(PolicyVersion.version)).where(PolicyVersion.policy_id == policy_id)
    )
    curr_max = max_ver_res.scalar() or 0
    next_version = curr_max + 1

    # Format rules
    rules_payload = {"rules": [r.model_dump() for r in data.rules]}

    version = PolicyVersion(
        policy_id=policy_id,
        version=next_version,
        status=PolicyVersionStatus.draft.value,
        rules=rules_payload,
        published_at=None,
    )
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def get_policy_version(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
) -> Optional[PolicyVersion]:
    """Retrieve a specific policy version by ID, verifying organization isolation."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        return None

    query = select(PolicyVersion).where(
        PolicyVersion.policy_id == policy_id,
        PolicyVersion.id == version_id,
    )
    res = await session.execute(query)
    return res.scalar_one_or_none()


async def list_policy_versions(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
) -> List[PolicyVersion]:
    """List all versions for a policy ordered by version number descending."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(organization_id, policy_id)

    query = (
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    res = await session.execute(query)
    return list(res.scalars().all())


async def publish_policy_version(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
) -> PolicyVersion:
    """Publish a policy version, retiring any previously published version."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(organization_id, policy_id)

    version = await get_policy_version(session, organization_id, policy_id, version_id)
    if version is None:
        raise PolicyVersionNotFoundError(policy_id, version_id)

    # If already published, return idempotent
    if version.status == PolicyVersionStatus.published.value:
        return version

    # Retire any previously published versions of this policy
    prev_published_query = select(PolicyVersion).where(
        PolicyVersion.policy_id == policy_id,
        PolicyVersion.status == PolicyVersionStatus.published.value,
    )
    prev_res = await session.execute(prev_published_query)
    for prev_ver in prev_res.scalars().all():
        prev_ver.status = PolicyVersionStatus.retired.value
        session.add(prev_ver)

    # Publish target version
    now = datetime.now(timezone.utc)
    version.status = PolicyVersionStatus.published.value
    version.published_at = now

    # Also activate policy if in draft
    if policy.status == PolicyStatus.draft.value:
        policy.status = PolicyStatus.active.value
        session.add(policy)

    session.add(version)
    await session.flush()
    await session.refresh(version)

    from app.audit.service import record_security_event, AuditEventType, AuditOutcome
    await record_security_event(
        session=session,
        event_type=AuditEventType.POLICY_PUBLISHED,
        action="PUBLISH_POLICY_VERSION",
        organization_id=organization_id,
        resource_type="POLICY",
        resource_id=policy_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "policy_id": str(policy_id),
            "version_id": str(version_id),
            "version": version.version,
        },
    )

    return version


async def retire_policy_version(
    session: AsyncSession,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    version_id: uuid.UUID,
) -> PolicyVersion:
    """Retire an active or published policy version."""
    policy = await get_policy(session, organization_id, policy_id)
    if policy is None:
        raise PolicyNotFoundError(organization_id, policy_id)

    version = await get_policy_version(session, organization_id, policy_id, version_id)
    if version is None:
        raise PolicyVersionNotFoundError(policy_id, version_id)

    if version.status != PolicyVersionStatus.retired.value:
        version.status = PolicyVersionStatus.retired.value
        session.add(version)
        await session.flush()
        await session.refresh(version)

    return version


async def evaluate_policies(
    session: AsyncSession,
    organization_id: uuid.UUID,
    context: ActionContext,
) -> PolicyEvaluationResult:
    """Evaluate an action context against all active policies for the organization."""
    org_res = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_res.scalar_one_or_none()
    if org is None:
        raise OrganizationNotFoundError(organization_id)
    if org.status != OrganizationStatus.active.value:
        raise OrganizationSuspendedError(organization_id)

    return await PolicyEngine.evaluate(session, organization_id, context)
