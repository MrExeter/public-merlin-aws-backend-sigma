# services/metering/tests/test_aggregate_handler_component.py
import json
from datetime import datetime, timezone
import boto3
from moto import mock_aws
import services.metering.lambdas.aggregate.handler as agg_mod

class _FakeDatetime:
    @staticmethod
    def now(tz=None):
        return datetime(2025, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

@mock_aws
def test_aggregate_with_moto_creates_invoices(monkeypatch):
    # Set fixed time
    monkeypatch.setattr(agg_mod, "datetime", _FakeDatetime)

    # Create usage + invoices tables the handler reads from env
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

    # Seed usage items
    ddb_res = boto3.resource("dynamodb", region_name="us-west-1")
    usage = ddb_res.Table("UsageLogs-dev")
    usage.put_item(Item={"usage_id": "u1", "tenant_id": "t1", "token_count": 100})
    usage.put_item(Item={"usage_id": "u2", "tenant_id": "t2", "token_count": 200})
    usage.put_item(Item={"usage_id": "u3", "tenant_id": "t1", "token_count": 50})

    # Run handler
    resp = agg_mod.handler({}, None)
    assert resp["message"] == "ok"
    assert resp["period"] == "2025-08"
    assert resp["tenants"] == 2

    # Verify invoices
    invoices = ddb_res.Table("UsageInvoices-dev")
    t1 = invoices.get_item(Key={"invoice_id": "t1-2025-08"})["Item"]
    t2 = invoices.get_item(Key={"invoice_id": "t2-2025-08"})["Item"]
    assert t1["tenant_id"] == "t1" and t1["tokens"] == "150" and t1["status"] == "DRAFT"
    assert t2["tenant_id"] == "t2" and t2["tokens"] == "200" and t2["status"] == "DRAFT"
