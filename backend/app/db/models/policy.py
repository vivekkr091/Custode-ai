"""Policy SQLAlchemy model for organization-level security governance."""

import enum
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PolicyStatus(str, enum.Enum):
    """Lifecycle status of a policy container."""
    draft = "draft"
    active = "active"
    suspended = "suspended"
    archived = "archived"


class EnforcementMode(str, enum.Enum):
    """Enforcement mode controlling whether matched rules block actions."""
    enforce = "enforce"
    audit = "audit"


class Policy(Base):
    """Tenant-scoped security policy container with versioned rules."""

    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_policies_org_slug"),
        Index("ix_policies_organization_id", "organization_id"),
        Index("ix_policies_status", "status"),
        Index("ix_policies_slug", "slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PolicyStatus.draft.value,
    )
    enforcement_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EnforcementMode.enforce.value,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        lazy="noload",
    )
    versions: Mapped[list["PolicyVersion"]] = relationship(  # type: ignore[name-defined]
        "PolicyVersion",
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.version.desc()",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Policy id={self.id} org={self.organization_id} "
            f"slug={self.slug!r} status={self.status!r} mode={self.enforcement_mode!r}>"
        )
