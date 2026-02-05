# services/metering/tests/test_aggregator.py
import boto3
from moto import mock_aws
from datetime import datetime, timezone
import services.metering.lambdas.aggregate.handler as agg_handler_mod

class _FixedDatetime:
    @staticmethod
    def now(tz=None):
        return datetime(2025, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

@mock_aws
def test_aggregator_writes_invoices_per_tenant(monkeypatch):
    # --- isolate region/session/env so other tests can't affect us ---
    boto3.setup_default_session()                       # reset default session
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-1")
    monkeypatch.setenv("USAGE_LOGS_TABLE_NAME", "UsageLogs-dev")
    monkeypatch.setenv("USAGE_INVOICES_TABLE_NAME", "UsageInvoices-dev")

    # Fix time for deterministic "YYYY-MM"
    monkeypatch.setattr(agg_handler_mod, "datetime", _FixedDatetime)

    # Create tables in the SAME region the handler will use
    ddb = boto3.client("dynamodb", region_name="us-west-1")

    ddb.create_table(
        TableName="UsageLogs-dev",
        KeySchema=[{"AttributeName": "usage_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "usage_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.create_table(
        TableName="UsageInvoices-dev",
        KeySchema=[{"AttributeName": "invoice_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "invoice_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Sanity: ensure tables exist in this moto context
    assert set(ddb.list_tables()["TableNames"]) >= {"UsageLogs-dev", "UsageInvoices-dev"}

    # Seed usage items
    put = ddb.put_item
    put(TableName="UsageLogs-dev", Item={
        "usage_id": {"S": "u1"},
        "tenant_id": {"S": "tA"},
        "token_count": {"N": "5"},
        "endpoint": {"S": "/v1/usage/log"},
        "timestamp": {"S": "2025-08-01T00:00:00Z"},
    })
    put(TableName="UsageLogs-dev", Item={
        "usage_id": {"S": "u2"},
        "tenant_id": {"S": "tA"},
        "token_count": {"N": "7"},
        "endpoint": {"S": "/v1/usage/log"},
        "timestamp": {"S": "2025-08-01T01:00:00Z"},
    })
    put(TableName="UsageLogs-dev", Item={
        "usage_id": {"S": "u3"},
        "tenant_id": {"S": "tB"},
        "token_count": {"N": "3"},
        "endpoint": {"S": "/v1/usage/log"},
        "timestamp": {"S": "2025-08-02T00:00:00Z"},
    })

    # Run the aggregator (it will read env + use boto3.resource('dynamodb') in the same region)
    resp = agg_handler_mod.handler({}, None)
    assert resp["message"] == "ok"
    assert resp["period"] == "2025-08"
    assert resp["tenants"] == 2

    # Verify invoices were written
    ddb_res = boto3.resource("dynamodb", region_name="us-west-1")
    inv = ddb_res.Table("UsageInvoices-dev")

    tA = inv.get_item(Key={"invoice_id": "tA-2025-08"})["Item"]
    tB = inv.get_item(Key={"invoice_id": "tB-2025-08"})["Item"]

    assert tA["tenant_id"] == "tA" and tA["tokens"] == "12" and tA["status"] == "DRAFT"
    assert tB["tenant_id"] == "tB" and tB["tokens"] == "3"  and tB["status"] == "DRAFT"
