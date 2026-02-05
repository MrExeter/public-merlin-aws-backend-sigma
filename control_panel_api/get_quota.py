# control_panel_api/get_quota.py

import json
import os
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

# Global dynamodb so tests can monkeypatch get_quota.dynamodb
dynamodb = boto3.resource("dynamodb")

# Default table names (used as fallbacks)
USAGE_TABLE_DEFAULT = "UsageLogs"
TENANTS_TABLE_DEFAULT = "MerlinSigmaTenants"

TENANT_GSI = "tenant_id-ts-index"
DEFAULT_DAILY_LIMIT = 100  # simple default; plans-based limits can come later


def _dec_int(v, default=0):
    if v is None:
        return default
    if isinstance(v, Decimal):
        return int(v)
    return int(v)


def handler(event, context):
    try:
        tenant_id = event["pathParameters"]["tenantId"]

        # Read table names at CALL TIME so tests can override via env
        tenants_table_name = os.getenv("TENANTS_TABLE_NAME", TENANTS_TABLE_DEFAULT)
        usage_table_name = os.getenv("USAGE_TABLE_NAME", USAGE_TABLE_DEFAULT)

        tenants_table = dynamodb.Table(tenants_table_name)
        usage_table = dynamodb.Table(usage_table_name)

        # ---- Load quota row (missing is NOT a hard error here)
        tenant_resp = tenants_table.get_item(
            Key={"PK": f"tenant#{tenant_id}", "SK": "quota#v1"}
        )

        quota_item = tenant_resp.get("Item", {})  # fallback empty
        daily_limit = _dec_int(
            quota_item.get("max_requests_per_day"),
            DEFAULT_DAILY_LIMIT,
        )

        # ---- Load today's usage
        today = datetime.utcnow().date().isoformat()

        usage_resp = usage_table.query(
            IndexName=TENANT_GSI,
            KeyConditionExpression=Key("tenant_id").eq(tenant_id)
                                  & Key("timestamp").begins_with(today),
        )

        usage_items = usage_resp.get("Items", [])

        used_today = len(usage_items)
        remaining = max(daily_limit - used_today, 0)

        body = {
            "tenant_id": tenant_id,
            "date": today,
            "allowed_requests_per_day": daily_limit,
            "requests_used_today": used_today,
            "requests_remaining": remaining,
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, default=str),
        }

    except Exception as e:
        # For test_get_quota_internal_error, we deliberately bubble as 500
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
