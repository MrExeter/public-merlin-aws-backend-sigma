import os
import sys

# 🧪 1. Add local Lambda Layer path before importing any layer-based packages
# layer_path = os.path.join(os.path.dirname(__file__), "lambdas", "python")
layer_path = os.path.join(os.path.dirname(__file__), "python")

if os.path.isdir(layer_path):
    sys.path.insert(0, layer_path)

# ✅ 2. Now safe to import third-party libraries
import json
import stripe
import boto3
from boto3.dynamodb.conditions import Key

# 🧪 3. Load local environment variables (e.g. for dev)
# ✅ Load .env only if dotenv is installed (for local/dev testing)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env.local"))
except ImportError:
    pass


stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "price_dummy")

dynamodb = boto3.resource("dynamodb")
subscriptions_table = dynamodb.Table(os.environ["SUBSCRIPTIONS_TABLE"])

def handler(event, context):
    try:
        body = json.loads(event["body"])
        email = body["email"]
        tenant_id = body["tenant_id"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid input"})}

    try:
        customer = stripe.Customer.create(email=email, metadata={"tenant_id": tenant_id})
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{"price": PRICE_ID}],
            metadata={"tenant_id": tenant_id}
        )

        subscriptions_table.put_item(Item={
            "tenant_id": tenant_id,
            "stripe_customer_id": customer.id,
            "subscription_id": subscription.id,
            "status": subscription.status,
        })

        return {
            "statusCode": 200,
            "body": json.dumps({
                "customer_id": customer.id,
                "subscription_id": subscription.id,
                "status": subscription.status
            })
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
