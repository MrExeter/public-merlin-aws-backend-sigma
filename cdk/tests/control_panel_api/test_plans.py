# cdk/tests/control_panel_api/test_plans.py

import json
from types import SimpleNamespace

import pytest

from control_panel_api import list_plans, get_plan_by_id, create_plan, update_plan
from .utils.fake_dynamo import (
    FakeTable,
    FakeDynamoResource,
    lambda_context,
    plans_table_name,
)


# ----------------------------------------------------------------------
# GET /plans
# ----------------------------------------------------------------------


def test_get_plans_ok(monkeypatch, lambda_context, plans_table_name):
    fake_items = [
        {"plan_id": "plan_free", "name": "Free", "description": "Free plan"},
        {"plan_id": "plan_pro", "name": "Pro", "description": "Pro plan"},
    ]

    fake_table = FakeTable(scan_items=fake_items)
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    # Patch boto3 in the list_plans module
    monkeypatch.setattr(
        list_plans, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    event = {"httpMethod": "GET", "path": "/plans"}

    resp = list_plans.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert len(body["plans"]) == 2
    assert body["plans"][0]["plan_id"] == "plan_free"


def test_get_plans_empty(monkeypatch, lambda_context, plans_table_name):
    fake_table = FakeTable(scan_items=[])
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        list_plans, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    event = {"httpMethod": "GET", "path": "/plans"}

    resp = list_plans.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 0
    assert body["plans"] == []


# ----------------------------------------------------------------------
# GET /plans/{planId}
# ----------------------------------------------------------------------


def test_get_plan_by_id_ok(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import get_plan_by_id

    plan_item = {
        "plan_id": "plan_free",
        "name": "Free",
        "description": "Default free plan",
        "limits": {"max_requests_per_day": 100},
    }

    fake_table = FakeTable(get_item=plan_item)
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        get_plan_by_id, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/plans/plan_free",
        "pathParameters": {"planId": "plan_free"},
    }

    resp = get_plan_by_id.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["plan_id"] == "plan_free"
    assert body["name"] == "Free"


def test_get_plan_by_id_not_found(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import get_plan_by_id

    fake_table = FakeTable(get_item=None)
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        get_plan_by_id, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    event = {
        "httpMethod": "GET",
        "path": "/plans/plan_unknown",
        "pathParameters": {"planId": "plan_unknown"},
    }

    resp = get_plan_by_id.handler(event, lambda_context)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert "not found" in body["error"].lower()


# ----------------------------------------------------------------------
# POST /plans
# ----------------------------------------------------------------------


def test_create_plan_ok(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import create_plan

    fake_table = FakeTable()
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        create_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    payload = {
        "plan_id": "plan_pro",
        "name": "Pro",
        "description": "Pro tier",
        "limits": {"max_requests_per_day": 1000},
    }

    event = {
        "httpMethod": "POST",
        "path": "/plans",
        "body": json.dumps(payload),
    }

    resp = create_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 201

    body = json.loads(resp["body"])
    assert body["plan_id"] == "plan_pro"
    assert body["name"] == "Pro"


def test_create_plan_invalid_body(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import create_plan

    fake_table = FakeTable()
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        create_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    event = {
        "httpMethod": "POST",
        "path": "/plans",
        "body": "not-json",
    }

    resp = create_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "invalid json" in body["error"].lower()


# ----------------------------------------------------------------------
# PUT /plans/{planId}
# ----------------------------------------------------------------------


def test_update_plan_ok(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import update_plan

    existing_item = {
        "plan_id": "plan_free",
        "name": "Free",
        "description": "Old desc",
        "limits": {"max_requests_per_day": 100},
    }

    class TrackingTable(FakeTable):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.last_put_item = None

        def get_item(self, Key=None, **kwargs):
            if self.get_item_value:
                return {"Item": self.get_item_value}
            return {}

        def put_item(self, Item=None, **kwargs):
            self.last_put_item = Item
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    fake_table = TrackingTable(get_item=existing_item)
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        update_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    payload = {
        "description": "New desc",
        "limits": {"max_requests_per_day": 200},
    }

    event = {
        "httpMethod": "PUT",
        "path": "/plans/plan_free",
        "pathParameters": {"planId": "plan_free"},
        "body": json.dumps(payload),
    }

    resp = update_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["description"] == "New desc"
    assert body["limits"]["max_requests_per_day"] == 200


def test_update_plan_not_found(monkeypatch, lambda_context, plans_table_name):
    from control_panel_api import update_plan

    fake_table = FakeTable(get_item=None)
    fake_dynamo = FakeDynamoResource({plans_table_name: fake_table})

    monkeypatch.setattr(
        update_plan, "boto3", SimpleNamespace(resource=lambda *_: fake_dynamo)
    )
    monkeypatch.setenv("PLANS_TABLE_NAME", plans_table_name)

    payload = {"description": "Does not matter"}
    event = {
        "httpMethod": "PUT",
        "path": "/plans/plan_missing",
        "pathParameters": {"planId": "plan_missing"},
        "body": json.dumps(payload),
    }

    resp = update_plan.handler(event, lambda_context)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert "not found" in body["error"].lower()
