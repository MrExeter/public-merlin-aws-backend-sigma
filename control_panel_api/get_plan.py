import os
import json
import boto3
from boto3.dynamodb.conditions import Key

DEFAULT_PLAN = "plan_free"

def handler(event, context):
    print("DEBUG get_plan loaded from:", __file__)

    tenant_id = event["pathParameters"]["tenantId"]

    tenants_table_name = os.environ.get("TENANTS_TABLE")
    plans_table_name = os.environ.get("PLANS_TABLE")

    if not tenants_table_name or not plans_table_name:
        raise RuntimeError("TENANTS_TABLE or PLANS_TABLE environment variable not set")

    # boto3 initialized INSIDE handler
    dynamodb = boto3.resource("dynamodb")
    tenants_table = dynamodb.Table(tenants_table_name)
    plans_table = dynamodb.Table(plans_table_name)

    # look up plan row for tenant
    resp = tenants_table.query(
        KeyConditionExpression=Key("PK").eq(f"tenant#{tenant_id}") &
                               Key("SK").eq("plan#current")
    )

    if resp.get("Items"):
        plan_id = resp["Items"][0]["plan_id"]
    else:
        plan_id = DEFAULT_PLAN

    plan_resp = plans_table.get_item(Key={"plan_id": plan_id})
    plan_data = plan_resp.get("Item", {})

    return {
        "statusCode": 200,
        "body": json.dumps({
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "plan": plan_data
        }, default=str)
    }
