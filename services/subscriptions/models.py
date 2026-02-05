from pydantic import BaseModel, Field, field_validator
from typing import Literal
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

class Subscription(BaseModel):
    subscription_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    plan_id: str
    start_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: Literal["active", "cancelled", "past_due"] = "active"
    paid_amount_usd: Decimal

    @field_validator("paid_amount_usd", mode="before")
    @classmethod
    def parse_paid_amount(cls, v):
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except Exception as e:
            raise ValueError(f"Invalid paid_amount_usd: {v}") from e

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}
