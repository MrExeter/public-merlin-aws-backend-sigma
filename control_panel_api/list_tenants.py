import os
import json
import base64
import boto3
from boto3.dynamodb.conditions import Attr


def _decode_cursor(cursor: str):
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def _encode_cursor(lek: dict):
    raw = json.dumps(lek, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def handler(event, context):
    # DEBUG TRACE
    print("DEBUG: list_tenants loaded from:", __file__)

    # --------------------------------------------------
    # ENVIRONMENT VARIABLE (set in CDK)
    # --------------------------------------------------
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise RuntimeError("TABLE_NAME environment variable not set")

    # --------------------------------------------------
    # IMPORTANT: allocate DynamoDB *inside* handler
    # (monkeypatch can override boto3 before this runs)
    # --------------------------------------------------
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # --------------------------------------------------
    # Parse input
    # --------------------------------------------------
    params = event.get("queryStringParameters") or {}

    try:
        limit = int(params.get("limit", "25"))
        limit = max(1, min(limit, 200))
    except ValueError:
        limit = 25

    cursor = params.get("cursor")
    eks = _decode_cursor(cursor) if cursor else None

    # --------------------------------------------------
    # SCAN all tenants: PK begins with "tenant#"
    # --------------------------------------------------
    scan_kwargs = {
        "ProjectionExpression": "PK, SK",
        "FilterExpression": Attr("PK").begins_with("tenant#"),
        "Limit": limit
    }

    if eks:
        scan_kwargs["ExclusiveStartKey"] = eks

    resp = table.scan(**scan_kwargs)
    items = resp.get("Items", [])

    # --------------------------------------------------
    # Aggregate into:
    # {"tenant_id": "t1", "entities": {"profile": "profile#v1"}}
    # --------------------------------------------------
    by_tenant = {}

    for it in items:
        pk = it["PK"]               # tenant#someId
        sk = it["SK"]               # profile#v1 / quota#v1 / usage#
        tenant_id = pk.split("#", 1)[1]

        ent_kind = sk.split("#", 1)[0]
        entry = by_tenant.setdefault(tenant_id, {"tenant_id": tenant_id, "entities": {}})
        entry["entities"][ent_kind] = sk

    tenants = sorted(by_tenant.values(), key=lambda x: x["tenant_id"])

    body = {
        "tenants": tenants,
        "count": len(tenants),
    }

    lek = resp.get("LastEvaluatedKey")
    if lek:
        body["next_cursor"] = _encode_cursor(lek)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }
