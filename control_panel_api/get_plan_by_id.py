import json
import os

import boto3

PLANS_TABLE_NAME = os.getenv("PLANS_TABLE_NAME", "PlansTable")


def handler(event, context):
    """
    GET /plans/{planId}
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

        table_name = os.getenv("PLANS_TABLE_NAME", PLANS_TABLE_NAME)
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        resp = table.get_item(Key={"plan_id": plan_id})
        item = resp.get("Item")
        if not item:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "plan not found"}),
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(item, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}, default=str),
        }
