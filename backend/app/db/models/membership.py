"""Organization Membership SQLAlchemy model.

Maps the M:N relationship between User and Organization.
Roles here are *human organisation roles* only — completely separate from
the future agent permission / tool authorisation system.
"""

import enum
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MembershipRole(str, enum.Enum):
    organization_admin = "organization_admin"
    security_analyst = "security_analyst"
    developer = "developer"
    viewer = "viewer"


class MembershipStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class Membership(Base):
    """Junction table linking a User to an Organization with a role."""

    __tablename__ = "memberships"
    __table_args__ = (
        # A user can only hold one membership per organisation.
        UniqueConstraint(
            "organization_id", "user_id", name="uq_memberships_org_user"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MembershipStatus.active.value,
    )

    # Relationships — loaded explicitly to prevent N+1 issues.
    organization: Mapped["Organization"] = relationship(  # type: ignore[name-defined]
        "Organization",
        back_populates="memberships",
        lazy="noload",
    )
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        back_populates="memberships",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<Membership org={self.organization_id} "
            f"user={self.user_id} role={self.role!r}>"
        )
