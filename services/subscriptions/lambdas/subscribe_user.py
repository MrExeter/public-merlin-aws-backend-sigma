# services/subscriptions/lambdas/subscribe_user.py

import json
from services.subscriptions.models import Subscription
from services.subscriptions.crud import create_subscription
from shared.utils.json_encoders import json_dumps_safe

def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        print("DEBUG BODY:", body)
        sub = Subscription(**body)
        item = create_subscription(sub)
        return {
            "statusCode": 201,
            "body": json_dumps_safe(item)
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json_dumps_safe({"error": str(e)})
        }
