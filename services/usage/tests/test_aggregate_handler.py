import json
from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
from services.usage.lambdas.aggregate import handler

def make_event(qs=None, claims=None):
    return {
        "queryStringParameters": qs or {},
        "requestContext": {"authorizer": {"claims": claims or {}}},
    }

def test_handler_happy_path(monkeypatch):
    fake_table = MagicMock()
    fake_table.query.return_value = {
        "Items": [
            {"user_id": "u1", "token_count": 5},
            {"user_id": "u2", "token_count": 3},
        ]
    }
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenant123")

    resp = handler.handler(make_event(), None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["tenant_id"] == "tenant123"
    assert body["count"] == 2
    assert body["total_tokens"] == "8"
    assert body["by_user"]["u1"] == "5"


def test_handler_empty_items(monkeypatch):
    fake_table = MagicMock()
    fake_table.query.return_value = {"Items": []}
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenantX")

    resp = handler.handler(make_event(), None)
    body = json.loads(resp["body"])
    assert body["count"] == 0
    assert body["total_tokens"] == "0"
    assert body["by_user"] == {}


def test_handler_with_user_filter(monkeypatch):
    captured_params = {}
    def fake_query(**kwargs):
        nonlocal captured_params
        captured_params = kwargs
        return {"Items": []}

    fake_table = MagicMock()
    fake_table.query.side_effect = fake_query
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenantY")

    resp = handler.handler(make_event(qs={"user_id": "u99"}), None)
    assert resp["statusCode"] == 200
    assert "FilterExpression" in captured_params


def test_handler_paginates(monkeypatch):
    calls = []
    def fake_query(**kwargs):
        if not calls:
            calls.append(1)
            return {
                "Items": [{"user_id": "u1", "token_count": 2}],
                "LastEvaluatedKey": {"k": "v"},
            }
        else:
            return {"Items": [{"user_id": "u1", "token_count": 3}]}

    fake_table = MagicMock()
    fake_table.query.side_effect = fake_query
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenantZ")

    resp = handler.handler(make_event(), None)
    body = json.loads(resp["body"])
    assert body["count"] == 2  # two items total
    assert body["total_tokens"] == "5"
    assert body["by_user"]["u1"] == "5"


def test_handler_missing_query_params(monkeypatch):
    """If queryStringParameters is missing, handler should still run safely."""
    fake_table = MagicMock()
    fake_table.query.return_value = {"Items": []}
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenantM")

    event = {"requestContext": {"authorizer": {"claims": {}}}}  # no queryStringParameters
    resp = handler.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["count"] == 0


def test_handler_missing_claims(monkeypatch):
    """
    If claims are missing, handler still returns 200 with no items,
    instead of erroring.
    """
    fake_table = MagicMock()
    fake_table.query.return_value = {"Items": []}
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: None)

    event = {"queryStringParameters": {}, "requestContext": {"authorizer": {}}}
    resp = handler.handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["count"] == 0


def test_handler_dynamodb_failure(monkeypatch):
    """If DynamoDB query fails, the handler currently bubbles up Exception."""
    fake_table = MagicMock()
    fake_table.query.side_effect = Exception("DDB error")
    monkeypatch.setattr(handler, "_tables", lambda: (fake_table, None))
    monkeypatch.setattr(handler, "_resolve_tenant", lambda e, t: "tenantD")

    event = {"queryStringParameters": {}, "requestContext": {"authorizer": {"claims": {}}}}
    with pytest.raises(Exception, match="DDB error"):
        handler.handler(event, None)



def test_tables_missing_env(monkeypatch):
    monkeypatch.delenv("USAGE_TABLE_NAME", raising=False)
    with pytest.raises(RuntimeError, match="USAGE_TABLE_NAME not set"):
        handler._tables()

def test_resolve_tenant_no_client(monkeypatch):
    event = {"requestContext": {"authorizer": {"claims": {}}}}
    tenant = handler._resolve_tenant(event, tenants_tbl=None)
    assert tenant == "unknown"


def test_resolve_tenant_ddb_exception(monkeypatch):
    fake_table = MagicMock()
    fake_table.get_item.side_effect = Exception("boom")
    event = {"requestContext": {"authorizer": {"claims": {"client_id": "abc"}}}}
    tenant = handler._resolve_tenant(event, fake_table)
    assert tenant == "unknown"


def test_parse_iso_invalid_returns_fallback():
    fallback = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dt = handler._parse_iso("invalid", fallback)
    assert dt == fallback

def test_tables_initializes_once(monkeypatch):
    fake_ddb = MagicMock()
    fake_ddb.Table.return_value = "tbl"
    monkeypatch.setattr(handler, "_ddb", lambda: fake_ddb)
    monkeypatch.setenv("USAGE_TABLE_NAME", "X")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "Y")
    t1, t2 = handler._tables()
    assert t1 == "tbl"
    assert t2 == "tbl"  # same mock reused


