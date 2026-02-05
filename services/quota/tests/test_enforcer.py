# services/quota/enforcer.py

import os
import boto3
from decimal import Decimal, getcontext
from typing import Optional
from unittest.mock import patch, MagicMock

from services.common.ddb_utils import ddb_safe
from services.common.time_utils import now_utc, now_utc_iso  # <-- add now_utc
from services.usage.aggregation import aggregate_usage_for_user
from services.quota.plans_limits import get_plan_limits
from services.quota import enforcer

class QuotaStatus:
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"

QUOTA_TABLE_NAME = os.getenv("QUOTA_TABLE_NAME", "QuotaState")
_dynamo = boto3.resource("dynamodb")
_quota_tbl = _dynamo.Table(QUOTA_TABLE_NAME)

getcontext().prec = 28
def _dec(x): return x if isinstance(x, Decimal) else Decimal(str(x))

def write_quota_state(*, tenant_id: str, period_label: str, plan_cap, used_tokens):
    limit = _dec(plan_cap)
    used  = _dec(used_tokens)
    remaining = limit - used
    used_pct  = _dec(0) if limit == 0 else (used / limit * _dec(100))
    item = {
        "tenant_id": tenant_id,
        "period": period_label,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "used_pct": used_pct,
        "updated_at": now_utc_iso(),
    }
    _quota_tbl.put_item(Item=ddb_safe(item))  # DDB-safe: no floats/datetimes

def check_quota(user_id: str, plan_id: str, tokens_to_use: int, dynamodb: Optional[object] = None) -> str:
    # Use a DATE for daily aggregation (YYYY-MM-DD), not a full ISO timestamp
    today = now_utc().date().isoformat()  # e.g., "2025-08-16"

    limits_raw = get_plan_limits(plan_id)
    # Keep everything as Decimal
    max_tokens   = _dec(limits_raw["max_tokens_per_day"])
    max_requests = _dec(limits_raw["max_requests_per_day"])

    usage = aggregate_usage_for_user(user_id, today, dynamodb)  # expects date, not full ISO

    total_tokens   = _dec(usage.tokens_used) + _dec(tokens_to_use)
    total_requests = _dec(usage.requests) + _dec(1)

    if total_tokens > max_tokens or total_requests > max_requests:
        return QuotaStatus.BLOCKED

    token_ratio   = total_tokens / max_tokens if max_tokens > 0 else _dec(0)
    request_ratio = total_requests / max_requests if max_requests > 0 else _dec(0)

    # Compare with Decimal to avoid float creep
    if max(token_ratio, request_ratio) > _dec("0.8"):
        return QuotaStatus.WARNING

    return QuotaStatus.ALLOWED


@patch("services.quota.enforcer.get_plan_limits")
@patch("services.quota.enforcer.aggregate_usage_for_user")
def test_allows_under_quota(mock_usage, mock_limits):
    mock_limits.return_value = {"max_tokens_per_day": 100, "max_requests_per_day": 10}
    mock_usage.return_value = MagicMock(tokens_used=10, requests=1)

    result = enforcer.check_quota("u1", "basic", tokens_to_use=5)
    assert result == enforcer.QuotaStatus.ALLOWED


@patch("services.quota.enforcer.get_plan_limits")
@patch("services.quota.enforcer.aggregate_usage_for_user")
def test_warning_near_limit(mock_usage, mock_limits):
    mock_limits.return_value = {"max_tokens_per_day": 100, "max_requests_per_day": 10}
    mock_usage.return_value = MagicMock(tokens_used=80, requests=5)

    result = enforcer.check_quota("u1", "basic", tokens_to_use=5)
    assert result == enforcer.QuotaStatus.WARNING


@patch("services.quota.enforcer.get_plan_limits")
@patch("services.quota.enforcer.aggregate_usage_for_user")
def test_blocks_when_exceeded(mock_usage, mock_limits):
    mock_limits.return_value = {"max_tokens_per_day": 100, "max_requests_per_day": 10}
    mock_usage.return_value = MagicMock(tokens_used=120, requests=12)

    result = enforcer.check_quota("u1", "basic", tokens_to_use=1)
    assert result == enforcer.QuotaStatus.BLOCKED


@patch("services.quota.enforcer.get_plan_limits")
@patch("services.quota.enforcer.aggregate_usage_for_user")
def test_blocks_when_tokens_exceeded(mock_usage, mock_limits):
    mock_limits.return_value = {"max_tokens_per_day": 50, "max_requests_per_day": 10}
    mock_usage.return_value = MagicMock(tokens_used=49, requests=0)

    result = enforcer.check_quota("u1", "basic", tokens_to_use=5)
    assert result == enforcer.QuotaStatus.BLOCKED


@patch("services.quota.enforcer._quota_tbl")
@patch("services.quota.enforcer.now_utc_iso", return_value="2025-09-25T00:00:00Z")
def test_write_quota_state_persists(mock_now, mock_tbl):
    # Mock put_item
    mock_tbl.put_item.return_value = {}

    enforcer.write_quota_state(
        tenant_id="t1", period_label="2025-09-25",
        plan_cap=100, used_tokens=40
    )

    args, kwargs = mock_tbl.put_item.call_args
    item = kwargs["Item"]

    assert item["tenant_id"] == "t1"
    assert item["limit"] == Decimal(100)
    assert item["used"] == Decimal(40)
    assert item["remaining"] == Decimal(60)
    assert item["used_pct"] == Decimal("40")
    assert item["updated_at"] == "2025-09-25T00:00:00Z"

