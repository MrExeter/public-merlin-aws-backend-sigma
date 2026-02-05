import json
import os

import boto3

PLANS_TABLE_NAME = os.getenv("PLANS_TABLE_NAME", "PlansTable")


def handler(event, context):
    """
    PUT /plans/{planId}

    Body JSON (all optional; only provided fields are updated):
      {
        "name": "...",
        "description": "...",
        "limits": {...}
      }
    """
    try:
        path_params = event.get("pathParameters") or {}
        plan_id = path_params.get("planId")
        if not plan_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "planId is required"}),
            }

        try:
            body = json.loads(event.get("body") or "")
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON payload"}),
            }

        table_name = os.getenv("PLANS_TABLE_NAME", PLANS_TABLE_NAME)
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # Load existing
        resp = table.get_item(Key={"plan_id": plan_id})
        existing = resp.get("Item")
        if not existing:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "plan not found"}),
            }

        # Merge updates
        updated = dict(existing)
        for field in ("name", "description", "limits"):
            if field in body:
                updated[field] = body[field]

        # For simplicity just overwrite via put_item – FakeTable supports this
        table.put_item(Item=updated)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(updated, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}, default=str),
        }
