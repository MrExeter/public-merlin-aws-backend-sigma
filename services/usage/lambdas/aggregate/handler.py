import os, json, decimal, boto3
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr

_DDB = None; _TBL = None; _TENANTS = None

def _ddb():
    global _DDB
    if _DDB is None: _DDB = boto3.resource("dynamodb")
    return _DDB

def _tables():
    global _TBL, _TENANTS
    if _TBL is None:
        name = os.getenv("USAGE_TABLE_NAME") or ""
        if not name: raise RuntimeError("USAGE_TABLE_NAME not set")
        _TBL = _ddb().Table(name)
    if _TENANTS is None and os.getenv("TENANTS_TABLE_NAME"):
        _TENANTS = _ddb().Table(os.environ["TENANTS_TABLE_NAME"])
    return _TBL, _TENANTS

def _resolve_tenant(event, tenants_tbl):
    claims = (event.get("requestContext", {}).get("authorizer", {}).get("claims", {}))
    client_id = claims.get("client_id") or claims.get("aud")
    if not client_id or not tenants_tbl: return "unknown"
    try:
        r = tenants_tbl.get_item(Key={"client_id": client_id})
        return (r.get("Item") or {}).get("tenant_id", "unknown")
    except Exception:
        return "unknown"

def _parse_iso(s, fallback):
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:
        return fallback

def handler(event, context):
    tbl, tenants_tbl = _tables()

    qs = event.get("queryStringParameters") or {}
    now = datetime.now(timezone.utc)
    start_dt = _parse_iso(qs.get("start", ""), (now - timedelta(days=7)).replace(microsecond=0))
    end_dt   = _parse_iso(qs.get("end",   ""), now.replace(microsecond=0))
    user_filter = qs.get("user_id")

    start = start_dt.isoformat(); end = end_dt.isoformat()
    tenant_id = _resolve_tenant(event, tenants_tbl)

    params = {
        "IndexName": "tenant_id-ts-index",
        "KeyConditionExpression": Key("tenant_id").eq(tenant_id) & Key("timestamp").between(start, end),
    }
    if user_filter:
        params["FilterExpression"] = Attr("user_id").eq(user_filter)

    total = decimal.Decimal(0); by_user = {}; count = 0
    while True:
        resp = tbl.query(**params)
        for it in resp.get("Items", []):
            tk = decimal.Decimal(str(it.get("token_count", 0)))
            total += tk
            u = it.get("user_id", "unknown")
            by_user[u] = by_user.get(u, decimal.Decimal(0)) + tk
            count += 1
        if "LastEvaluatedKey" not in resp: break
        params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    body = {
        "tenant_id": tenant_id, "start": start, "end": end,
        "count": count, "total_tokens": str(total),
        "by_user": {u: str(v) for u, v in by_user.items()},
    }
    return {"statusCode": 200, "body": json.dumps(body)}
