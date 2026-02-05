import pytest
from decimal import Decimal
from datetime import datetime, timezone
from services.usage import models

def test_usage_record_serialization_roundtrip():
    rec = models.UsageRecord(
        user_id="u1",
        plan_id="p1",
        endpoint="/x",
        tokens_used=10,
        duration_ms=5,
        success=True,
        cost_usd=Decimal("1.23"),
    )
    ddb_item = rec.for_dynamodb()
    assert ddb_item["user_id"] == "u1"
    assert "timestamp" in ddb_item
    assert isinstance(ddb_item["cost_usd"], float) or isinstance(ddb_item["cost_usd"], Decimal)

def test_usage_record_accepts_str_timestamp():
    ts = "2025-09-25T12:00:00Z"
    rec = models.UsageRecord(
        user_id="u2",
        plan_id="p2",
        endpoint="/y",
        tokens_used=5,
        duration_ms=2,
        success=False,
        timestamp=ts,
    )
    assert isinstance(rec.timestamp, datetime)

def test_usage_summary_defaults_and_serialization():
    summary = models.UsageSummary(user_id="u3")
    assert summary.tokens_used == 0
    assert summary.requests == 0
    assert isinstance(float(summary.cost_usd), float)
