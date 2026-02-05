# services/plans/lambdas/create_plan.py

import json
from services.plans.models import Plan
from services.plans.crud import create_plan
from shared.utils.json_encoders import json_dumps_safe


def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        plan = Plan(**body)
        item = create_plan(plan)
        return {
            "statusCode": 201,
            "body": json_dumps_safe(item)
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json_dumps_safe({"error": str(e)})
        }
