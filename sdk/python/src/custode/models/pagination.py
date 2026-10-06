"""Pagination generic models for CUSTODE SDK."""

from typing import Generic, List, Optional, TypeVar
from pydantic import Field

from custode.models.base import CUSTODEModel

T = TypeVar("T")


class PaginatedList(CUSTODEModel, Generic[T]):
    """Generic container for paginated API query responses."""

    items: List[T] = Field(default_factory=list)
    total: int = 0
    limit: Optional[int] = None
    offset: Optional[int] = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> T:
        return self.items[index]
