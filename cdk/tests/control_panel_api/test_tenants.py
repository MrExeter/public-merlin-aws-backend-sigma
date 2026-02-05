import json
import pytest
from types import SimpleNamespace
from .utils.fake_dynamo import (FakeTable,
                                FakeDynamoResource,
                                lambda_context,
                                plans_table_name,
                                tenants_table_name)

from control_panel_api import list_tenants, get_plan, put_plan


# =====================================================================
# Shared Fixtures
# =====================================================================

# @pytest.fixture
# def tenants_table_name():
#     return "FakeTenants"
#
#
# @pytest.fixture
# def plans_table_name():
#     return "FakePlans"
#
#
# @pytest.fixture
# def lambda_context():
#     return SimpleNamespace(function_name="test_fn")


# =====================================================================
# TESTS: LIST TENANTS
# =====================================================================

def test_list_tenants_ok(monkeypatch, tenants_table_name, lambda_context):
    """GET /tenants should return list of tenants."""

    fake_items = [
        {"PK": "tenant#tenant3012", "SK": "profile#v1"},
        {"PK": "tenant#tenant42",   "SK": "profile#v1"},
    ]

    fake_tenant_table = FakeTable(scan_items=fake_items)
    fake_dynamo = FakeDynamoResource({tenants_table_name: fake_tenant_table})

    monkeypatch.setattr(list_tenants, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TABLE_NAME", tenants_table_name)

    event = {"httpMethod": "GET", "path": "/tenants"}

    resp = list_tenants.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert len(body["tenants"]) == 2
    assert body["tenants"][0]["tenant_id"] == "tenant3012"


# =====================================================================
# TESTS: GET PLAN
# =====================================================================

def test_get_plan_ok(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """GET /tenants/{id}/plan should return plan data."""

    fake_tenant_row = {"PK": "tenant#tenant3012", "SK": "plan#current", "plan_id": "plan_free"}
    fake_plan_row = {"plan_id": "plan_free", "name": "Free Tier", "description": "Free plan"}

    fake_tenant_table = FakeTable(query_items=[fake_tenant_row])
    fake_plans_table = FakeTable(get_item=fake_plan_row)

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plans_table
    })

    # inject fake boto
    monkeypatch.setattr(get_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))

    # inject required environment variables
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {"pathParameters": {"tenantId": "tenant3012"}}

    resp = get_plan.handler(event, lambda_context)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["tenant_id"] == "tenant3012"
    assert body["plan_id"] == "plan_free"
    assert body["plan"]["name"] == "Free Tier"


# =====================================================================
# TESTS: PUT PLAN
# =====================================================================

def test_put_plan_ok(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """PUT /tenants/{id}/plan should update the tenant's plan."""

    # initial tenant plan
    fake_tenant_row = {"PK": "tenant#tenant3012", "SK": "plan#current", "plan_id": "plan_free"}
    fake_plan_row = {"plan_id": "plan_pro", "name": "Pro Tier"}

    fake_tenant_table = FakeTable(get_item=fake_tenant_row)
    fake_plans_table = FakeTable(get_item=fake_plan_row)

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plans_table
    })

    monkeypatch.setattr(put_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))

    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {
        "httpMethod": "PUT",
        "path": "/tenants/tenant3012/plan",
        "pathParameters": {"tenantId": "tenant3012"},
        "body": json.dumps({"plan_id": "plan_pro"})
    }

    resp = put_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["tenant_id"] == "tenant3012"
    assert body["new_plan"] == "plan_pro"
    assert body["status"] == "success"


# =====================================================================
# TESTS: LIST TENANTS — ERROR & EDGE CASES
# =====================================================================

def test_list_tenants_missing_env(monkeypatch, lambda_context):
    """If TABLE_NAME isn't set, the handler must raise RuntimeError."""
    # remove env var
    monkeypatch.delenv("TABLE_NAME", raising=False)

    event = {"httpMethod": "GET", "path": "/tenants"}

    with pytest.raises(RuntimeError) as exc:
        list_tenants.handler(event, lambda_context)

    assert "TABLE_NAME" in str(exc.value)


def test_list_tenants_invalid_limit(monkeypatch, tenants_table_name, lambda_context):
    """If limit isn't an integer, fall back to default (25) and still succeed."""
    fake_items = [
        {"PK": "tenant#x", "SK": "profile#v1"},
        {"PK": "tenant#y", "SK": "profile#v1"},
    ]

    fake_tenant_table = FakeTable(scan_items=fake_items)
    fake_dynamo = FakeDynamoResource({tenants_table_name: fake_tenant_table})

    # env + fake boto
    monkeypatch.setenv("TABLE_NAME", tenants_table_name)
    monkeypatch.setattr(list_tenants, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))

    event = {
        "httpMethod": "GET",
        "path": "/tenants",
        "queryStringParameters": {"limit": "not-a-number"}
    }

    resp = list_tenants.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert len(body["tenants"]) == 2


def test_list_tenants_dynamo_error(monkeypatch, tenants_table_name, lambda_context):
    """If DynamoDB raises an exception, bubble it up as a RuntimeError (or 500 if caught)."""

    class ExplodingTable:
        def scan(self, **kwargs):
            raise Exception("boom")

    fake_dynamo = FakeDynamoResource({tenants_table_name: ExplodingTable()})

    monkeypatch.setenv("TABLE_NAME", tenants_table_name)
    monkeypatch.setattr(list_tenants, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))

    event = {"httpMethod": "GET", "path": "/tenants"}

    # list_tenants does not catch exceptions → should raise
    with pytest.raises(Exception) as exc:
        list_tenants.handler(event, lambda_context)

    assert "boom" in str(exc.value)


# =====================================================================
# TESTS: GET PLAN — ERROR & EDGE CASES
# =====================================================================

def test_get_plan_missing_tenants_env(monkeypatch, plans_table_name, lambda_context):
    """TENANTS_TABLE missing should raise RuntimeError."""
    monkeypatch.delenv("TENANTS_TABLE", raising=False)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {"pathParameters": {"tenantId": "tenant3012"}}

    with pytest.raises(RuntimeError):
        get_plan.handler(event, lambda_context)


def test_get_plan_missing_plans_env(monkeypatch, tenants_table_name, lambda_context):
    """PLANS_TABLE missing should raise RuntimeError."""
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.delenv("PLANS_TABLE", raising=False)

    event = {"pathParameters": {"tenantId": "tenant3012"}}

    with pytest.raises(RuntimeError):
        get_plan.handler(event, lambda_context)


def test_get_plan_default_when_no_plan_row(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """
    If tenant isn't assigned a plan row (no plan#current item),
    handler should fall back to DEFAULT_PLAN = 'plan_free'.
    """

    fake_tenant_table = FakeTable(query_items=[])  # no plan entry
    fake_plan_table = FakeTable(get_item={"plan_id": "plan_free", "name": "Free Tier"})

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plan_table
    })

    monkeypatch.setattr(get_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {"pathParameters": {"tenantId": "tenant3012"}}
    resp = get_plan.handler(event, lambda_context)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["plan_id"] == "plan_free"
    assert body["plan"]["name"] == "Free Tier"


def test_get_plan_missing_plan_record(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """
    If the plan row doesn't exist in the plans table,
    handler should return an empty plan object {}.
    """

    fake_tenant_row = {"PK": "tenant#tenant3012", "SK": "plan#current", "plan_id": "plan_pro"}

    fake_tenant_table = FakeTable(query_items=[fake_tenant_row])
    fake_plan_table = FakeTable(get_item=None)  # plan not found

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plan_table
    })

    monkeypatch.setattr(get_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {"pathParameters": {"tenantId": "tenant3012"}}

    resp = get_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["plan_id"] == "plan_pro"
    assert body["plan"] == {}  # empty object


# =====================================================================
# TESTS: PUT PLAN — ERROR & EDGE CASES
# =====================================================================

def test_put_plan_missing_tenants_env(monkeypatch, plans_table_name, lambda_context):
    """TENANTS_TABLE missing should raise RuntimeError."""
    monkeypatch.delenv("TENANTS_TABLE", raising=False)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": json.dumps({"plan_id": "plan_pro"})
    }

    with pytest.raises(RuntimeError):
        put_plan.handler(event, lambda_context)


def test_put_plan_missing_plans_env(monkeypatch, tenants_table_name, lambda_context):
    """PLANS_TABLE missing should raise RuntimeError."""
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.delenv("PLANS_TABLE", raising=False)

    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": json.dumps({"plan_id": "plan_pro"})
    }

    with pytest.raises(RuntimeError):
        put_plan.handler(event, lambda_context)


def test_put_plan_tenant_not_found(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """If tenant row doesn't exist, return 404."""
    fake_tenant_table = FakeTable(get_item=None)
    fake_plan_table = FakeTable(get_item={"plan_id": "plan_pro", "name": "Pro Tier"})

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plan_table
    })

    monkeypatch.setattr(put_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": json.dumps({"plan_id": "plan_pro"})
    }

    resp = put_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 404
    assert "tenant not found" in resp["body"]


def test_put_plan_plan_not_found(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """If plan row doesn't exist in Plans table, return 404."""
    fake_tenant_row = {"PK": "tenant#tenant3012", "SK": "plan#current", "plan_id": "plan_free"}

    fake_tenant_table = FakeTable(get_item=fake_tenant_row)
    fake_plans_table = FakeTable(get_item=None)  # plan not found

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plans_table
    })

    monkeypatch.setattr(put_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": json.dumps({"plan_id": "plan_pro"})
    }

    resp = put_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 404
    assert "plan not found" in resp["body"]



# =====================================================================
# TESTS: PUT PLAN — BODY VALIDATION
# =====================================================================

def test_put_plan_malformed_json(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """PUT /tenants/{id}/plan → malformed JSON returns 400."""
    fake_tenant_table = FakeTable(get_item={"client_id": "tenant3012", "plan_id": "free"})
    fake_plan_table = FakeTable(get_item={"plan_id": "plan_pro", "name": "Pro"})

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plan_table
    })

    monkeypatch.setattr(put_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    # malformed JSON
    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": '{"plan_id": "plan_pro"'   # ← missing closing brace
    }

    resp = put_plan.handler(event, lambda_context)

    assert resp["statusCode"] == 400
    assert "invalid json" in resp["body"].lower()


def test_put_plan_missing_plan_id(monkeypatch, tenants_table_name, plans_table_name, lambda_context):
    """PUT /tenants/{id}/plan → missing plan_id → 400."""
    fake_tenant_table = FakeTable(get_item={"client_id": "tenant3012", "plan_id": "free"})
    fake_plan_table = FakeTable(get_item={"plan_id": "plan_pro", "name": "Pro"})

    fake_dynamo = FakeDynamoResource({
        tenants_table_name: fake_tenant_table,
        plans_table_name: fake_plan_table
    })

    monkeypatch.setattr(put_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo))
    monkeypatch.setenv("TENANTS_TABLE", tenants_table_name)
    monkeypatch.setenv("PLANS_TABLE", plans_table_name)

    # missing plan_id
    event = {
        "pathParameters": {"tenantId": "tenant3012"},
        "body": '{}'
    }

    resp = put_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 400
    assert "plan_id" in resp["body"].lower()


