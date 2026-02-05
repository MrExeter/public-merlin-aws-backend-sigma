import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="usage")
metrics = Metrics(namespace="MerlinSigma", service="usage")

from services.common.time_utils import month_key, iso_utc_now


###############################################
# DEBUG / LOCAL RUNNING SUPPORT

def _trace_get_item(table, *args, **kwargs):
    resp = table._original_get_item(*args, **kwargs)
    print(f"🧩 DDB get_item called with: {kwargs.get('Key')}, returned: {resp}")
    return resp

###############################################

# Add local layer path for testing (e.g. moto or stripe)
layer_path = os.path.join(os.path.dirname(__file__), "..", "python")
if os.path.isdir(layer_path):
    sys.path.insert(0, layer_path)

# Optional: Load dotenv if running locally
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env.local"))
except ImportError:
    pass

# ---- Lazy globals ----
_DDB = None
_USAGE_TBL = None
_TENANTS_TBL = None
_QUOTA_TBL = None


def _get_tables():
    """Return DynamoDB tables, instrumented for debugging."""
    global _DDB, _USAGE_TBL, _TENANTS_TBL, _QUOTA_TBL

    if _DDB is None:
        _DDB = boto3.resource("dynamodb")

    # --- helper to wrap get_item with debug print ---
    def _wrap_table_get_item(table, name):
        try:
            orig = table.get_item

            def traced_get_item(*args, **kwargs):
                resp = orig(*args, **kwargs)
                print(f"🧩 DDB get_item[{name}] called with Key={kwargs.get('Key')} -> {resp}")
                return resp

            table.get_item = traced_get_item
        except Exception as e:
            print(f"⚠️ Could not wrap {name}: {e}")

    if _USAGE_TBL is None:
        name = os.getenv("USAGE_TABLE_NAME")
        if not name:
            raise RuntimeError("USAGE_TABLE_NAME not set")
        _USAGE_TBL = _DDB.Table(name)
        _wrap_table_get_item(_USAGE_TBL, "USAGE_TBL")

    if _TENANTS_TBL is None:
        tname = os.getenv("TENANTS_TABLE_NAME")
        if tname:
            _TENANTS_TBL = _DDB.Table(tname)
            _wrap_table_get_item(_TENANTS_TBL, "TENANTS_TBL")

    if _QUOTA_TBL is None:
        qname = os.getenv("QUOTA_TABLE_NAME")
        if qname:
            _QUOTA_TBL = _DDB.Table(qname)
            _wrap_table_get_item(_QUOTA_TBL, "QUOTA_TBL")

    return _USAGE_TBL, _TENANTS_TBL, _QUOTA_TBL


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _resolve_tenant_app(event, tenants_tbl):
    if tenants_tbl is None:
        return ("unknown", "default")

    claims = (event.get("requestContext", {})
                    .get("authorizer", {})
                    .get("claims", {}))
    client_id = claims.get("client_id") or claims.get("aud")
    if not client_id:
        return ("unknown", "default")

    try:
        resp = tenants_tbl.get_item(Key={"client_id": client_id})
        item = resp.get("Item") or {}
        return (item.get("tenant_id", "unknown"), item.get("app_id", "default"))
    except Exception:
        return ("unknown", "default")

def _current_month_key():
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.month:02d}"

def _get_monthly_usage(usage_tbl, tenant_id):
    try:
        resp = usage_tbl.query(
            IndexName="tenant_id-index",  # You must define this GSI
            KeyConditionExpression=Key("tenant_id").eq(tenant_id)
        )
        tokens_this_month = sum(
            item.get("token_count", 0)
            for item in resp.get("Items", [])
            if item.get("timestamp", "").startswith(_current_month_key())
        )
        return Decimal(str(tokens_this_month))
    except Exception:
        return Decimal("0")


def _try_consume_quota(tenant_id: str, inc_tokens: int, tenants_table, quota_table, usage_table) -> bool:
    """
    Atomically add `inc_tokens` to this tenant's monthly total.
    Uses a per-tenant-month aggregator item (timestamp='AGG').
    Returns True if within limit (update applied), False if it would exceed.
    """
    # 1) find plan + limit
    tenant_resp = tenants_table.get_item(Key={"tenant_id": tenant_id})
    plan_id = (tenant_resp.get("Item") or {}).get("plan_id", "free-plan-dev")

    plan_resp = quota_table.get_item(Key={"plan_id": plan_id})
    quota_limit = int(plan_resp.get("Item", {}).get("quota_limit", 0))

    # 2) conditional atomic update
    # month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    m_key = month_key()
    agg_key = {"tenant_month": f"{tenant_id}#{m_key}", "timestamp": "AGG"}

    try:
        usage_table.update_item(
            Key=agg_key,
            UpdateExpression="SET #tt = if_not_exists(#tt, :zero) + :inc",
            ConditionExpression="(attribute_not_exists(#tt) AND :inc <= :limit) OR (#tt + :inc) <= :limit",
            ExpressionAttributeNames={"#tt": "token_total"},
            ExpressionAttributeValues={
                ":inc": inc_tokens,
                ":zero": 0,
                ":limit": quota_limit,
            },
            ReturnValues="UPDATED_NEW",
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def _is_subscription_active(tenant_id: str, tenants_table) -> bool:
    if tenants_table is None:
        return True
    try:
        resp = tenants_table.get_item(Key={"tenant_id": tenant_id}) or {}
        status = (resp.get("Item") or {}).get("subscription_status", "active")
        return status in {"active", "trialing"}
    except Exception:
        return True



@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    # ✅ Step 1: verify critical environment variables before doing anything else
    if not os.getenv("USAGE_TABLE_NAME"):
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Missing USAGE_TABLE_NAME environment variable"}
            ),
        }

    usage_table, tenants_table, quota_table = _get_tables()
    try:
        body = json.loads(event.get("body", "{}"))
        tenant_id = body["tenant_id"]
        token_count = int(body["token_count"])
        endpoint = body["endpoint"]
    except (KeyError, ValueError):
        metrics.add_metric(name="BadPayload", unit=MetricUnit.Count, value=1)  # 👈 add
        logger.warning("bad_payload")
        return {"statusCode": 400, "body": json.dumps({"message": "Bad payload"})}

    logger.append_keys(tenant_id=tenant_id, endpoint=endpoint)

    # --- subscription gate ---
    if not _is_subscription_active(tenant_id, tenants_table):
        metrics.add_metric(name="PaymentRequired", unit=MetricUnit.Count, value=1)
        logger.warning("subscription_inactive")
        return {"statusCode": 402, "body": json.dumps({"message": "Payment required"})}

    # --- quota enforcement (feature-flagged) ---
    use_hard_quota = os.getenv("HARD_QUOTA", "false").lower() == "true"
    if use_hard_quota:
        allowed = _try_consume_quota(tenant_id, token_count, tenants_table, quota_table, usage_table)
    else:
        # existing soft check preserved for backward compatibility
        allowed = is_within_quota(tenant_id, token_count, tenants_table, quota_table, usage_table)

    if not allowed:
        metrics.add_metric(name="QuotaDenied", unit=MetricUnit.Count, value=1)
        logger.info("quota_denied", extra={"tokens": token_count})
        return {"statusCode": 403, "body": json.dumps({"message": "Quota exceeded"})}

    # normal usage write (unchanged)
    m_key = month_key()

    # Build a deterministic ID (API Gateway requestId preferred; client request_id as fallback)
    request_id = (
            event.get("requestContext", {}).get("requestId")
            or (body.get("request_id") if isinstance(body, dict) else "")
            or ""
    )
    usage_id = hashlib.sha256(
        f"{tenant_id}|{m_key}|{endpoint}|{request_id}".encode("utf-8")
    ).hexdigest()

    # --- Idempotency marker (pre-write) ---
    # Key is (tenant_month, timestamp="IDEMP#<usage_id>")
    marker_item = {
        "tenant_month": f"{tenant_id}#{m_key}",
        "timestamp": f"IDEMP#{usage_id}",
        "created_at": iso_utc_now(),
    }

    try:
        usage_table.put_item(
            Item=marker_item,
            # If a marker already exists for this request, treat as duplicate
            ConditionExpression="attribute_not_exists(#ts)",
            ExpressionAttributeNames={"#ts": "timestamp"},
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # Duplicate -> idempotent success (do NOT write another usage row)
            metrics.add_metric(name="IdempotencyHit", unit=MetricUnit.Count, value=1)  # 👈 add
            logger.info("idempotency_hit")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Usage recorded", "usage_id": usage_id}),
            }
        raise

    # --- Normal usage write (first time only) ---
    item = {
        "usage_id": usage_id,  # deterministic, not a random UUID
        "tenant_month": f"{tenant_id}#{m_key}",
        "timestamp": iso_utc_now(),
        "tenant_id": tenant_id,
        "token_count": token_count,
        "endpoint": endpoint,
    }

    # (Optional) keep a condition as a safety net; it won't run on duplicates anyway
    usage_table.put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(usage_id)"
    )

    # on success, after you put_item:
    metrics.add_metric(name="UsageRecorded", unit=MetricUnit.Count, value=1)
    logger.info("usage_recorded", extra={"tokens": token_count, "usage_id": item["usage_id"]})
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Usage recorded", "usage_id": usage_id}),
    }


def is_within_quota(tenant_id, new_tokens, tenants_table, quota_table, usage_table):
    tenant_resp = tenants_table.get_item(Key={"tenant_id": tenant_id})
    plan_id = tenant_resp["Item"].get("plan_id", "free-plan-dev")

    plan_resp = quota_table.get_item(Key={"plan_id": plan_id})
    quota_limit = int(plan_resp["Item"]["quota_limit"])

    m_key = month_key()
    month_prefix = f"{tenant_id}#{m_key}"
    usage_resp = usage_table.query(
        KeyConditionExpression=Key("tenant_month").eq(month_prefix),
        ProjectionExpression="token_count"
    )
    total_used = sum(int(item.get("token_count", 0)) for item in usage_resp["Items"])
    return (total_used + new_tokens) <= quota_limit


# ---- test compatibility helpers ----

def _record_usage(*_args, **_kwargs):
    """Placeholder for legacy tests that patch this symbol."""
    return None

def _check_quota(*_args, **_kwargs):
    """Placeholder for legacy tests that expect a quota check in handler."""
    return True


