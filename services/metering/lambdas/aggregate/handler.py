# services/metering/lambdas/aggregate/handler.py

import os, uuid, decimal, boto3
from datetime import datetime, timezone

_DDB = None
_USAGE_TBL = None
_INVOICES_TBL = None

def _get_tables():
    global _DDB, _USAGE_TBL, _INVOICES_TBL
    if _DDB is None:
        _DDB = boto3.resource("dynamodb")
    if _USAGE_TBL is None:
        name = os.getenv("USAGE_LOGS_TABLE_NAME")
        if not name:
            raise RuntimeError("USAGE_LOGS_TABLE_NAME not set")
        _USAGE_TBL = _DDB.Table(name)
    if _INVOICES_TBL is None:
        name = os.getenv("USAGE_INVOICES_TABLE_NAME")
        if not name:
            raise RuntimeError("USAGE_INVOICES_TABLE_NAME not set")
        _INVOICES_TBL = _DDB.Table(name)
    return _USAGE_TBL, _INVOICES_TBL

def handler(event, context):
    usage_tbl, invoices_tbl = _get_tables()

    # Aggregate tokens by tenant_id (fallback to "unknown")
    totals = {}
    scan_kwargs = {}
    while True:
        resp = usage_tbl.scan(**scan_kwargs)
        for it in resp.get("Items", []):
            tenant = it.get("tenant_id", "unknown")
            tokens = decimal.Decimal(str(it.get("token_count", 0)))
            totals[tenant] = totals.get(tenant, decimal.Decimal(0)) + tokens
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    now = datetime.now(timezone.utc)
    period_label = now.strftime("%Y-%m")
    created = 0

    for tenant_id, token_sum in totals.items():
        invoice_id = f"{tenant_id}-{period_label}"  # deterministic per (tenant, month)
        item = {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
            "period_label": period_label,
            "tokens": str(token_sum),              # keep as string to avoid float issues
            "status": "DRAFT",
            "estimated_aws_cost_usd": "0.00",
            "created_at": now.isoformat(),
        }
        invoices_tbl.put_item(Item=item)
        created += 1

    return {"message": "ok", "period": period_label, "tenants": created}
