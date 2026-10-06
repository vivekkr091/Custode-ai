"""Authorization Decision models for CUSTODE SDK."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field

from custode.models.base import CUSTODEModel


class DecisionType(str, Enum):
    """Authoritative authorization decision states."""

    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class Decision(CUSTODEModel):
    """Immutable authoritative authorization decision record produced by the CUSTODE engine."""

    id: str
    organization_id: str
    runtime_action_id: str
    decision: str
    reason: str
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None
    permission_effect: Optional[str] = None
    policy_effect: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version_id: Optional[str] = None
    factors: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_trace: Dict[str, Any] = Field(default_factory=dict)
    engine_version: Optional[str] = None
    created_at: Any

    @property
    def is_allowed(self) -> bool:
        """True if the action is fully authorized and permitted to execute."""
        return self.decision.lower() == DecisionType.ALLOW.value

    @property
    def is_blocked(self) -> bool:
        """True if the action was denied by permissions, policy, or critical security findings."""
        return self.decision.lower() == DecisionType.BLOCK.value

    @property
    def requires_approval(self) -> bool:
        """True if the action requires human review before execution can proceed."""
        return self.decision.lower() == DecisionType.REQUIRE_APPROVAL.value


class DecisionList(CUSTODEModel):
    """Paginated collection of authorization decisions."""

    items: List[Decision] = Field(default_factory=list)
    total: int = 0

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> Decision:
        return self.items[index]
