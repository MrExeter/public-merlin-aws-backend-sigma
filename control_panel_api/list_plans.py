import json
import os

import boto3

PLANS_TABLE_NAME = os.getenv("PLANS_TABLE_NAME", "PlansTable")


def handler(event, context):
    """
    GET /plans

    Returns all plans from the plans table.

    Test-friendly:
    - Table name comes from PLANS_TABLE_NAME env var.
    - boto3 is imported at module level so tests can monkeypatch list_plans.boto3.
    """
    try:
        table_name = os.getenv("PLANS_TABLE_NAME", PLANS_TABLE_NAME)
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        resp = table.scan()
        items = resp.get("Items", [])

        body = {
            "plans": items,
            "count": len(items),
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}, default=str),
        }
