"""SecurityFinding SQLAlchemy model representing a normalized security finding detected by Sentinel."""

from typing import Any, Dict, Optional
import uuid

from sqlalchemy import Float, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SecurityFinding(Base):
    """Authoritative normalized security finding produced during payload inspection."""

    __tablename__ = "security_findings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runtime_actions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("security_scans.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    interaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("llm_interactions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    mcp_server_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_servers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    mcp_tool_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mcp_tools.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Finding classification & details
    scanner: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scan_direction: Mapped[str] = mapped_column(String(20), nullable=False, default="INPUT", server_default="INPUT", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="sentinel")

    finding_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Explicit relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    runtime_action: Mapped[Optional["RuntimeAction"]] = relationship(  # type: ignore[name-defined]
        "RuntimeAction",
        lazy="noload",
    )
    scan: Mapped[Optional["SecurityScan"]] = relationship(  # type: ignore[name-defined]
        "SecurityScan",
        back_populates="findings",
        lazy="noload",
    )
    interaction: Mapped[Optional["LLMInteraction"]] = relationship(  # type: ignore[name-defined]
        "LLMInteraction",
        back_populates="findings",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_security_findings_org_severity", "organization_id", "severity"),
        Index("ix_security_findings_org_category", "organization_id", "category"),
        Index("ix_security_findings_org_action", "organization_id", "runtime_action_id"),
        Index("ix_security_findings_org_direction", "organization_id", "scan_direction"),
        Index("ix_security_findings_org_created_at", "organization_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<SecurityFinding id={self.id} org={self.organization_id} "
            f"cat={self.category} sev={self.severity} title={self.title!r}>"
        )
