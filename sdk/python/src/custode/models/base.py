"""Base Pydantic model for CUSTODE SDK."""

from pydantic import BaseModel, ConfigDict


class CUSTODEModel(BaseModel):
    """Base model that safely ignores extra/unknown response fields and permits alias population."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
