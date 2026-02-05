import json
import uuid
from decimal import Decimal
from datetime import datetime
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("UsageLogs")


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        usage_id = str(uuid.uuid4())

        item = {
            "usage_id": usage_id,
            "user_id": body["user_id"],
            "token_count": Decimal(str(body["token_count"])),
            "endpoint": body["endpoint"],
            "timestamp": body.get("timestamp") or datetime.utcnow().isoformat()
        }

        table.put_item(Item=item)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Usage recorded", "usage_id": usage_id}, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
