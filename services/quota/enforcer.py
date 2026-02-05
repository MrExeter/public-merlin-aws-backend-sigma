# services/quota/enforcer.py

import os
import boto3
from decimal import Decimal, getcontext
from typing import Optional

from services.common.ddb_utils import ddb_safe
from services.common.time_utils import now_utc, now_utc_iso  # <- use now_utc for date
from services.usage.aggregation import aggregate_usage_for_user
from services.quota.plans_limits import get_plan_limits


class QuotaStatus:
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"

QUOTA_TABLE_NAME = os.getenv("QUOTA_TABLE_NAME", "QuotaState")
_dynamo = boto3.resource("dynamodb")
_quota_tbl = _dynamo.Table(QUOTA_TABLE_NAME)

getcontext().prec = 28
def _dec(x):
    return x if isinstance(x, Decimal) else Decimal(str(x))


def write_quota_state(*, tenant_id: str, period_label: str, plan_cap, used_tokens):
    limit = _dec(plan_cap)
    used  = _dec(used_tokens)
    remaining = limit - used
    used_pct  = _dec(0) if limit == 0 else (used / limit * _dec(100))

    item = {
        "tenant_id": tenant_id,
        "period": period_label,   # e.g. "2025-08"
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "used_pct": used_pct,
        "updated_at": now_utc_iso(),
    }
    _quota_tbl.put_item(Item=ddb_safe(item))  # DDB-safe: no floats/datetimes


def check_quota(user_id: str, plan_id: str, tokens_to_use: int, dynamodb: Optional[object] = None) -> str:
    # Use a DATE for aggregation window, not a full ISO timestamp
    today = now_utc().date().isoformat()      # e.g. "2025-08-16"

    limits = get_plan_limits(plan_id)
    usage = aggregate_usage_for_user(user_id, today, dynamodb)

    total_tokens = _dec(usage.tokens_used) + _dec(tokens_to_use)
    total_requests = _dec(usage.requests) + _dec(1)

    if total_tokens > _dec(limits["max_tokens_per_day"]) or total_requests > _dec(limits["max_requests_per_day"]):
        return QuotaStatus.BLOCKED

    token_ratio = total_tokens / _dec(limits["max_tokens_per_day"])
    request_ratio = total_requests / _dec(limits["max_requests_per_day"])

    print(f"Token ratio: {token_ratio}, Request ratio: {request_ratio}")

    if max(token_ratio, request_ratio) > _dec("0.8"):
        return QuotaStatus.WARNING

    return QuotaStatus.ALLOWED
