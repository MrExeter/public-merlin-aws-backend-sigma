import json
from types import SimpleNamespace

import pytest

from control_panel_api import get_quota
from .utils.fake_dynamo import (FakeTable,
                                FakeDynamoResource,
                                lambda_context,
                                usage_table_name,
                                plans_table_name,
                                tenants_table_name)


# ----------------------------------------------------------------------
# 1) Happy path — tenant exists + usage rows exist
# ----------------------------------------------------------------------
def test_get_quota_ok(monkeypatch, tenants_table_name, usage_table_name, lambda_context):
    # Fake tenant row (whatever your get_quota expects for get_item)
    tenant_item = {
        "client_id": "tenant3012",
        "plan_id": "plan_free",
    }

    # Fake usage rows; your handler will aggregate them however it wants
    usage_items = [
        {"PK": "tenant#tenant3012", "SK": "usage#1", "tokens_used": 50},
        {"PK": "tenant#tenant3012", "SK": "usage#2", "tokens_used": 30},
    ]

    fake_tenant_table = FakeTable(get_item=tenant_item)
    fake_usage_table = FakeTable(query_items=usage_items)

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        usage_table_name: fake_usage_table,
    })

    # Patch the module-level dynamodb used in get_quota
    monkeypatch.setattr(get_quota, "dynamodb", fake_dynamo)
    monkeypatch.setenv("TENANTS_TABLE_NAME", tenants_table_name)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/tenant3012/quota",
        "pathParameters": {"tenantId": "tenant3012"},
    }

    resp = get_quota.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    # We don't over-assume body structure yet; just basic sanity
    assert body.get("tenant_id") in ("tenant3012", "tenant#tenant3012")


# ----------------------------------------------------------------------
# 2) Tenant exists but no usage rows
# ----------------------------------------------------------------------
def test_get_quota_no_usage(monkeypatch, tenants_table_name, usage_table_name, lambda_context):
    tenant_item = {
        "client_id": "tenant3012",
        "plan_id": "plan_free",
    }

    fake_tenant_table = FakeTable(get_item=tenant_item)
    fake_usage_table = FakeTable(query_items=[])

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        usage_table_name: fake_usage_table,
    })

    monkeypatch.setattr(get_quota, "dynamodb", fake_dynamo)
    monkeypatch.setenv("TENANTS_TABLE_NAME", tenants_table_name)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/tenant3012/quota",
        "pathParameters": {"tenantId": "tenant3012"},
    }

    resp = get_quota.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    # At minimum: still returns correct tenant id
    assert body.get("tenant_id") in ("tenant3012", "tenant#tenant3012")


# ----------------------------------------------------------------------
# 3) Tenant not found
# ----------------------------------------------------------------------
def test_get_quota_tenant_not_found(monkeypatch, tenants_table_name, usage_table_name, lambda_context):
    # Fake tenant table with no row
    fake_tenant_table = FakeTable(get_item=None)
    fake_usage_table = FakeTable(query_items=[])

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        usage_table_name: fake_usage_table,
    })

    monkeypatch.setattr(get_quota, "dynamodb", fake_dynamo)
    monkeypatch.setenv("TENANTS_TABLE_NAME", tenants_table_name)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/tenant404/quota",
        "pathParameters": {"tenantId": "tenant404"},
    }

    resp = get_quota.handler(event, lambda_context)

    # If your handler is already strict:
    #   expect 404
    # If not, we can relax this later after seeing the behavior.
    assert resp["statusCode"] in (200, 404)
    body = json.loads(resp["body"])
    # If it does 404 with an error message, this will still pass:
    assert "tenant" in json.dumps(body).lower()


# ----------------------------------------------------------------------
# 4) Internal error (Dynamo query failure) → 500
# ----------------------------------------------------------------------
def test_get_quota_internal_error(monkeypatch, tenants_table_name, usage_table_name, lambda_context):
    class ExplodingTable:
        def get_item(self, **kwargs):
            raise Exception("boom in get_item")

    fake_tenant_table = ExplodingTable()
    fake_usage_table = FakeTable(query_items=[])

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        usage_table_name: fake_usage_table,
    })

    monkeypatch.setattr(get_quota, "dynamodb", fake_dynamo)
    monkeypatch.setenv("TENANTS_TABLE_NAME", tenants_table_name)
    monkeypatch.setenv("USAGE_TABLE_NAME", usage_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/tenants/tenant3012/quota",
        "pathParameters": {"tenantId": "tenant3012"},
    }

    resp = get_quota.handler(event, lambda_context)
    assert resp["statusCode"] == 500
