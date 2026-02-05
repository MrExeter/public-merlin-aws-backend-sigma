import json
import os
from uuid import uuid4

import boto3

PLANS_TABLE_NAME = os.getenv("PLANS_TABLE_NAME", "PlansTable")


def handler(event, context):
    """
    POST /plans

    Body JSON:
      {
        "plan_id": "plan_free",   # optional; will auto-generate if missing
        "name": "Free",
        "description": "Free tier",
        "limits": {...}
      }
    """
    try:
        table_name = os.getenv("PLANS_TABLE_NAME", PLANS_TABLE_NAME)
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        try:
            body = json.loads(event.get("body") or "")
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON payload"}),
            }

        plan_id = body.get("plan_id") or f"plan_{uuid4().hex[:8]}"
        name = body.get("name")
        description = body.get("description")
        limits = body.get("limits")

        if not name or limits is None:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "name and limits are required"}),
            }

        item = {
            "plan_id": plan_id,
            "name": name,
            "description": description or "",
            "limits": limits,
        }

        # In tests this goes through FakeTable.put_item()
        table.put_item(Item=item)

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(item, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}, default=str),
        }
