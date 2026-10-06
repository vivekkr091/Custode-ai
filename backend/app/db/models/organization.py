"""Organization SQLAlchemy model."""

import enum

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Organization(Base):
    """Top-level tenancy boundary.  Every agent and user belongs to an org."""

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrganizationStatus.active.value,
    )

    # Relationship: one org → many memberships (lazy="noload" — load explicitly)
    memberships: Mapped[list["Membership"]] = relationship(  # type: ignore[name-defined]
        "Membership",
        back_populates="organization",
        lazy="noload",
    )

    # Relationship: one org → many agents (lazy="noload" — load explicitly)
    agents: Mapped[list["Agent"]] = relationship(  # type: ignore[name-defined]
        "Agent",
        back_populates="organization",
        lazy="noload",
    )

    # Relationship: one org → many tools (lazy="noload" — load explicitly)
    tools: Mapped[list["Tool"]] = relationship(  # type: ignore[name-defined]
        "Tool",
        back_populates="organization",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug!r}>"
