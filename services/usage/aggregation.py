# services/usage/aggregation.py

import os
from decimal import Decimal
from typing import Optional, List
from boto3.resources.base import ServiceResource
from boto3.dynamodb.conditions import Key
from services.usage.models import UsageSummary

DEFAULT_USAGE_TABLE_NAME = "UsageLogs"

def get_usage_table_name() -> str:
    return os.getenv("USAGE_TABLE_NAME", DEFAULT_USAGE_TABLE_NAME)

def aggregate_usage_for_user(user_id: str, date_str: str, dynamodb: Optional[ServiceResource] = None) -> UsageSummary:
    if dynamodb is None:
        import boto3
        dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(get_usage_table_name())
    resp = table.query(
        IndexName="user_id-index",
        KeyConditionExpression=Key("user_id").eq(user_id) & Key("timestamp").begins_with(date_str),
    )
    items: List[dict] = resp.get("Items", [])
    total_tokens = sum(int(it.get("tokens_used", 0)) for it in items)
    total_requests = len(items)
    total_cost = sum(Decimal(str(it.get("cost_usd", "0.00"))) for it in items)

    return UsageSummary(
        user_id=user_id,
        date=date_str,
        tokens_used=total_tokens,
        requests=total_requests,
        cost_usd=total_cost,
    )
