# control_panel_api/get_usage.py

import json
import os
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")


def _dec(value):
    """Convert Decimal → int or float safely."""
    if isinstance(value, Decimal):
        try:
            return int(value)
        except:
            return float(value)
    return value


def handler(event, context):
    print("DEBUG get_usage loaded from:", __file__)

    # --------------------------------------------
    # LOAD TABLE NAME AT RUNTIME (fix for tests)
    # --------------------------------------------
    usage_table_name = os.environ.get("USAGE_TABLE_NAME")
    if not usage_table_name:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "USAGE_TABLE_NAME not set"})
        }

    table = dynamodb.Table(usage_table_name)

    # --------------------------------------------
    # VALIDATE tenantId
    # --------------------------------------------
    tenant_id = event.get("pathParameters", {}).get("tenantId")
    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "tenantId is required"})
        }

    # --------------------------------------------
    # QUERY USAGE
    # --------------------------------------------
    try:
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(f"tenant#{tenant_id}")
        )

        items = resp.get("Items", [])
        items = [{k: _dec(v) for k, v in it.items()} for it in items]

        return {
            "statusCode": 200,
            "body": json.dumps({"usage": items}, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
