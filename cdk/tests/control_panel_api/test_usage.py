import json
import pytest
from types import SimpleNamespace
from .utils.fake_dynamo import (FakeTable,
                                FakeDynamoResource,
                                lambda_context,
                                usage_table_name,
                                plans_table_name,
                                tenants_table_name)
from control_panel_api import list_tenants, get_plan, put_plan

# ------------------------------------------------------------------
# GET /tenants/{tenantId}/usage Tests
# ------------------------------------------------------------------

def test_get_usage_ok(monkeypatch, lambda_context, tenants_table_name, usage_table_name):
    from control_panel_api import get_usage

    fake_usage_items = [
        {"PK": "tenant#3012", "SK": "usage#2025-11-01", "tokens_used": 50},
        {"PK": "tenant#3012", "SK": "usage#2025-11-02", "tokens_used": 75},
    ]

    fake_usage_table = FakeTable(query_items=fake_usage_items)
    fake_dynamo = FakeDynamoResource({usage_table_name: fake_usage_table})

    monkeypatch.setattr(get_usage, "dynamodb", fake_dynamo)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/3012/usage",
        "pathParameters": {"tenantId": "3012"}
    }

    resp = get_usage.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert len(body["usage"]) == 2
    assert body["usage"][0]["tokens_used"] == 50


def test_get_usage_no_records(monkeypatch, lambda_context, tenants_table_name, usage_table_name):
    from control_panel_api import get_usage

    fake_usage_table = FakeTable(query_items=[])
    fake_dynamo = FakeDynamoResource({usage_table_name: fake_usage_table})

    monkeypatch.setattr(get_usage, "dynamodb", fake_dynamo)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/3012/usage",
        "pathParameters": {"tenantId": "3012"}
    }

    resp = get_usage.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["usage"] == []


def test_get_usage_missing_tenantId(monkeypatch, lambda_context, usage_table_name):
    from control_panel_api import get_usage

    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/x/usage",
        "pathParameters": {}
    }

    resp = get_usage.handler(event, lambda_context)
    assert resp["statusCode"] == 400


def test_get_usage_table_error(monkeypatch, lambda_context, usage_table_name):
    from control_panel_api import get_usage

    class ExplodingTable:
        def query(self, **_):
            raise Exception("boom")

    fake_dynamo = FakeDynamoResource({usage_table_name: ExplodingTable()})

    monkeypatch.setattr(get_usage, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/3012/usage",
        "pathParameters": {"tenantId": "3012"}
    }

    resp = get_usage.handler(event, lambda_context)
    assert resp["statusCode"] == 500



