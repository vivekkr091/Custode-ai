"""Service functions for User entity."""

from typing import Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User, UserStatus
from app.schemas.user import UserCreate


class EmailAlreadyExistsError(Exception):
    """Raised when a user email address is already in use."""
    def __init__(self, email: str):
        super().__init__(f"User with email '{email}' already exists")
        self.email = email


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    """Create a new user with normalized email address and optional password hash."""
    normalized_email = data.email.strip().lower()

    # Check if email exists
    query = select(User).where(User.email == normalized_email)
    result = await session.execute(query)
    if result.scalar_one_or_none() is not None:
        raise EmailAlreadyExistsError(normalized_email)

    pw_hash = hash_password(data.password) if data.password else None

    user = User(
        email=normalized_email,
        display_name=data.display_name.strip(),
        status=UserStatus.active.value,
        password_hash=pw_hash,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Retrieve a user by their primary key ID."""
    query = select(User).where(User.id == user_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()
