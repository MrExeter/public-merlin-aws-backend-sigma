import os
import json
import boto3

def handler(event, context):
    print("DEBUG put_plan loaded from:", __file__)

    tenants_table_name = os.environ.get("TENANTS_TABLE")
    plans_table_name = os.environ.get("PLANS_TABLE")

    if not tenants_table_name or not plans_table_name:
        raise RuntimeError("TENANTS_TABLE or PLANS_TABLE environment variable not set")

    dynamodb = boto3.resource("dynamodb")
    tenants_table = dynamodb.Table(tenants_table_name)
    plans_table = dynamodb.Table(plans_table_name)

    try:
        tenant_id = event["pathParameters"]["tenantId"]

        # --------------------------------------------
        # SAFE JSON PARSE (Fixes malformed JSON test)
        # --------------------------------------------
        raw_body = event.get("body") or ""
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON payload"})
            }

        # --------------------------------------------
        # Validate required field
        # --------------------------------------------
        new_plan_id = body.get("plan_id")
        if not new_plan_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "plan_id is required"})
            }

        # --------------------------------------------
        # Verify tenant exists using PK/SK schema
        # --------------------------------------------
        tenant_resp = tenants_table.get_item(
            Key={"PK": f"tenant#{tenant_id}", "SK": "plan#current"}
        )

        tenant_item = tenant_resp.get("Item")
        if not tenant_item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "tenant not found"})
            }

        old_plan = tenant_item.get("plan_id")

        # --------------------------------------------
        # Verify new plan exists
        # --------------------------------------------
        plan_resp = plans_table.get_item(Key={"plan_id": new_plan_id})
        if "Item" not in plan_resp:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "plan not found"})
            }

        # --------------------------------------------
        # Update tenant plan
        # --------------------------------------------
        tenants_table.put_item(
            Item={
                "PK": f"tenant#{tenant_id}",
                "SK": "plan#current",
                "plan_id": new_plan_id,
            }
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "tenant_id": tenant_id,
                "old_plan": old_plan,
                "new_plan": new_plan_id,
                "status": "success"
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
