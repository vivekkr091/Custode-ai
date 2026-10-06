"""Agent models for CUSTODE SDK."""

from typing import Optional
from custode.models.base import CUSTODEModel


class AuthenticatedAgent(CUSTODEModel):
    """Authoritative agent identity resolved from an agent API key."""

    organization_id: str
    agent_id: str
    credential_id: str


class Agent(CUSTODEModel):
    """Registered agent security identity."""

    id: str
    organization_id: str
    name: str
    slug: str
    description: Optional[str] = None
    agent_type: str
    status: str
    environment: str
    created_at: str
    updated_at: Optional[str] = None
