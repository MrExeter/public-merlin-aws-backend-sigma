import os
import sys

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

# 🧪 1. Add local Lambda Layer path before importing any layer-based packages
layer_path = os.path.join(os.path.dirname(__file__), "lambdas", "python")
if os.path.isdir(layer_path):
    sys.path.insert(0, layer_path)

# ✅ 2. Now safe to import third-party libraries
import json
import boto3

import stripe


# Compatibility shim for SignatureVerificationError
try:
    # New Stripe SDK (>=6.x)
    SignatureVerificationError = stripe.SignatureVerificationError
except AttributeError:
    try:
        # Old Stripe SDK (<6.x)
        from stripe.error import SignatureVerificationError  # type: ignore
    except ImportError:
        SignatureVerificationError = getattr(stripe, "SignatureVerificationError", None)


_sm = boto3.client("secretsmanager")
_SECRET_CACHE: dict[str, str] = {}

from botocore.exceptions import ClientError
from services.common.time_utils import now_utc_iso

logger = Logger(service="billing-webhook")
metrics = Metrics(namespace="MerlinSigma", service="billing-webhook")

# Load .env only when NOT on Lambda (safe for local/dev)
try:
    if not os.getenv("AWS_EXECUTION_ENV"):
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env.local"))
except Exception:
    pass


def _secret_from_sm(arn: str) -> str:
    # simple in-memory cache per execution environment
    if arn in _SECRET_CACHE:
        return _SECRET_CACHE[arn]
    resp = _sm.get_secret_value(SecretId=arn)
    if "SecretString" in resp:
        val = resp["SecretString"]
    else:
        # SecretBinary is bytes; decode to str (utf-8)
        val = resp["SecretBinary"]
        if isinstance(val, (bytes, bytearray)):
            val = val.decode("utf-8")
    _SECRET_CACHE[arn] = val
    return val

def _get_secret(key_env: str, arn_env: str) -> str:
    """Prefer direct env (dev/CI). Otherwise fetch from Secrets Manager ARN."""
    v = os.getenv(key_env)
    if v:
        return v
    arn = os.getenv(arn_env)
    if not arn:
        raise RuntimeError(f"Missing {key_env} or {arn_env}")
    return _secret_from_sm(arn)


def _get_events_table():
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-1")
    table_name = os.environ.get("STRIPE_EVENTS_TABLE", "StripeEvents")
    ddb = boto3.resource("dynamodb", region_name=region)
    return ddb.Table(table_name)


def _get_table():
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-1")
    table_name = os.environ.get("SUBSCRIPTIONS_TABLE", "SubscriptionsTable")
    ddb = boto3.resource("dynamodb", region_name=region)
    return ddb.Table(table_name)


@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    metrics.add_metric(name="WebhookReceived", unit=MetricUnit.Count, value=1)
    # 0) Read secrets (env in CI/local; Secrets Manager in AWS)
    secret = _get_secret("STRIPE_WEBHOOK_SECRET", "STRIPE_WEBHOOK_SECRET_ARN")
    stripe.api_key = _get_secret("STRIPE_SECRET_KEY", "STRIPE_SECRET_ARN")
    # 1) Extract raw body and signature header (case-insensitive)
    try:
        raw_body = event["body"]  # keep raw string for Stripe signature verification
        headers = event.get("headers") or {}
        sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not sig_header:
            return _response(400, "Missing signature header")
        if not isinstance(raw_body, str):
            # be defensive if something already parsed it upstream
            raw_body = json.dumps(raw_body)
    except Exception as e:
        return _response(400, f"Malformed event: {str(e)}")

    # 2) Construct the Stripe event ONCE using the raw body
    try:
        stripe_event = stripe.Webhook.construct_event(raw_body, sig_header, secret)
    except ValueError as e:
        return _response(400, f"Invalid payload: {str(e)}")
    except SignatureVerificationError:
        return _response(400, "Invalid signature")

    # 3) Idempotency marker per event.id (short-circuit duplicates)
    events_tbl = _get_events_table()
    event_id = stripe_event.get("id") or ""
    ev_type = stripe_event.get("type", "")
    logger.append_keys(stripe_event_id=event_id, stripe_event_type=ev_type)

    if not event_id:
        return _response(400, "Missing event id")

    try:
        events_tbl.put_item(
            Item={
                "event_id": event_id,
                "received_at": now_utc_iso(),
                "type": stripe_event.get("type", ""),
            },
            ConditionExpression="attribute_not_exists(event_id)",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # Duplicate delivery -> already processed or in-flight
            return _response(200, "ok")
        raise

    # 4) Process supported event types
    if stripe_event["type"] == "customer.subscription.updated":
        try:
            subscription = stripe_event["data"]["object"]
            customer_id = subscription["customer"]
            status = subscription["status"]
            # OK for now; we can switch to price.id later
            plan_id = subscription["items"]["data"][0]["plan"]["id"]
            tenant_id = get_tenant_id_from_customer(customer_id)

            subs_tbl = _get_table()
            subs_tbl.put_item(Item={
                "tenant_id": tenant_id,
                "stripe_customer_id": customer_id,
                "plan_id": plan_id,
                "status": status,
                "subscription_status": status,
                "last_updated": stripe_event["created"],
            })
            metrics.add_metric(name="WebhookProcessed", unit=MetricUnit.Count, value=1)
            logger.info("subscription_updated")
        except Exception as e:
            # Allow Stripe to retry by removing the marker on failure
            try:
                events_tbl.delete_item(Key={"event_id": event_id})
            except Exception:
                pass
            metrics.add_metric(name="WebhookError", unit=MetricUnit.Count, value=1)
            logger.error("subscription_update_failed", extra={"error": str(e)})
            return _response(500, f"Error saving subscription: {str(e)}")

    # 5) Done
    return _response(200, "ok")


def get_tenant_id_from_customer(customer_id):
    """
    Placeholder: map Stripe customer ID → tenant ID.
    Replace with actual lookup logic (e.g. DynamoDB).
    """
    return f"tenant-{customer_id[:6]}"

def _response(status, body):
    return {
        "statusCode": status,
        "body": json.dumps({"message": body})
    }

# 🧪 Local testing stub
if __name__ == "__main__":
    fake_event = {
        "headers": {
            "stripe-signature": "tbd"
        },
        "body": "{}"
    }
    print(handler(fake_event, None))
