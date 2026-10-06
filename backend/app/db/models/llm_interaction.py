"""LLMInteraction SQLAlchemy model representing a tracked, audited LLM invocation."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LLMInteraction(Base):
    """Authoritative persistent record of an LLM request processed through the CUSTODE LLM Gateway."""

    __tablename__ = "llm_interactions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runtime_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Identifiers & Targeting
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="dev", index=True)

    # Lifecycle & Security Status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # pending, evaluating, pending_approval, completed, blocked, output_blocked, failed
    input_scan_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="skipped",
    )  # clean, flagged, blocked, skipped
    output_scan_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="skipped",
    )  # clean, flagged, blocked, skipped

    # Governance & Assessment
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="allow",
        index=True,
    )  # allow, require_approval, block
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")

    # Performance & Tokens
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cryptographic Hashing & Forensic Previews (Raw prompts/responses are never permanently stored by default)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    output_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sanitized_prompt_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sanitized_output_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata & Timestamps
    interaction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    agent: Mapped["Agent"] = relationship(  # type: ignore[name-defined]
        "Agent",
        lazy="noload",
    )
    runtime_action: Mapped[Optional["RuntimeAction"]] = relationship(  # type: ignore[name-defined]
        "RuntimeAction",
        lazy="noload",
    )
    findings: Mapped[List["SecurityFinding"]] = relationship(  # type: ignore[name-defined]
        "SecurityFinding",
        back_populates="interaction",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_llm_interactions_org_created_at", "organization_id", "created_at"),
        Index("ix_llm_interactions_org_provider", "organization_id", "provider"),
        Index("ix_llm_interactions_org_status", "organization_id", "status"),
        Index("ix_llm_interactions_org_model", "organization_id", "model"),
    )

    def __repr__(self) -> str:
        return (
            f"<LLMInteraction id={self.id} org={self.organization_id} "
            f"provider={self.provider} model={self.model} status={self.status}>"
        )
