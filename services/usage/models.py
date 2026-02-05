from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, field_serializer

from services.common.ddb_utils import ddb_safe
from services.common.time_utils import now_utc, to_iso_z, parse_iso


class UsageRecord(BaseModel):
    usage_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    plan_id: str
    endpoint: str
    tokens_used: int
    duration_ms: int
    success: bool

    # store internally as timezone-aware UTC datetime
    timestamp: datetime = Field(default_factory=now_utc)

    cost_usd: Decimal = Decimal("0.00")

    # Accept both str and datetime (for back-compat/tests)
    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_ts(cls, v):
        if v is None:
            return now_utc()
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return parse_iso(v)
        return v

    # For API JSON responses: timestamp -> ISO-8601 Z
    @field_serializer("timestamp")
    def _ser_ts(self, v: datetime) -> str:
        return to_iso_z(v)

    # For API JSON responses: Decimal -> float
    @field_serializer("cost_usd")
    def _ser_cost(self, v: Decimal) -> float:
        return float(v)

    def for_dynamodb(self) -> dict:
        # Use python mode; don’t produce JSON types
        d = self.model_dump(mode="python")
        # Ensure timestamp is a string
        d["timestamp"] = to_iso_z(self.timestamp)
        # Recursively convert floats->Decimal, datetime->ISO, etc.
        return ddb_safe(d)


class UsageSummary(BaseModel):
    user_id: str
    # keep as string to avoid churn; store "YYYY-MM-DD"
    date: str = Field(default_factory=lambda: to_iso_z(now_utc())[:10])
    tokens_used: int = 0
    requests: int = 0
    cost_usd: Decimal = Decimal("0.00")

    @field_serializer("cost_usd")
    def _ser_cost(self, v: Decimal) -> float:
        return float(v)
