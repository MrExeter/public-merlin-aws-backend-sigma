# services/plans/models.py

from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
from decimal import Decimal
from pydantic import field_validator


class Plan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: Optional[str] = None
    price_usd: Decimal
    max_tokens: int
    active: bool = True

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_tokens must be greater than 0")
        return v

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


