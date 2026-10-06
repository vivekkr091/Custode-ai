"""SecurityScan SQLAlchemy model representing an authoritative Sentinel scan run on a RuntimeAction."""

from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SecurityScan(Base):
    """Persisted record of an automated security scan performed on a RuntimeAction by Sentinel."""

    __tablename__ = "security_scans"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runtime_actions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Aggregated Scan Metrics
    scanner_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    highest_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE", index=True)

    # Operational status & latency
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed", index=True)
    scanners_run: Mapped[List[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scan_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )

    # Explicit relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    runtime_action: Mapped["RuntimeAction"] = relationship(  # type: ignore[name-defined]
        "RuntimeAction",
        lazy="noload",
    )
    findings: Mapped[List["SecurityFinding"]] = relationship(  # type: ignore[name-defined]
        "SecurityFinding",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        Index("ix_security_scans_org_created_at", "organization_id", "created_at"),
        Index("ix_security_scans_org_action", "organization_id", "runtime_action_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<SecurityScan id={self.id} org={self.organization_id} "
            f"action={self.runtime_action_id} findings={self.findings_count} "
            f"highest={self.highest_severity}>"
        )
