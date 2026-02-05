# services/usage/tests/test_handler_quota.py
import json
import pytest
from unittest.mock import MagicMock
from services.usage.lambdas.log_usage.handler import handler

@pytest.fixture(autouse=True)
def quota_env(monkeypatch):
    # These envs are not strictly used in these unit tests because we mock _get_tables,
    # but keeping them set mirrors your runtime environment.
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageLogs-dev")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "Tenants-dev")
    monkeypatch.setenv("QUOTA_TABLE_NAME", "QuotaPlans-dev")

@pytest.fixture
def event_ok():
    return {
        "body": json.dumps({
            "tenant_id": "tenant-1",
            "token_count": 100,
            "endpoint": "/generate",
        })
    }

def _mk_tables(quota_limit: int, already_used: int = 0):
    """Build MagicMock tables as expected by handler._get_tables()."""
    usage_table = MagicMock()
    tenants_table = MagicMock()
    quota_table = MagicMock()

    tenants_table.get_item.return_value = {"Item": {"plan_id": "free-plan-dev"}}
    quota_table.get_item.return_value = {"Item": {"quota_limit": quota_limit}}
    usage_table.query.return_value = {"Items": [{"token_count": already_used}]}
    usage_table.put_item.return_value = {}

    return usage_table, tenants_table, quota_table

def test_quota_allows_request(monkeypatch, event_ok, lambda_ctx):
    usage_table, tenants_table, quota_table = _mk_tables(quota_limit=1_000_000, already_used=100)

    # Directly patch the module's _get_tables to return our MagicMocks
    monkeypatch.setattr(
        "services.usage.lambdas.log_usage.handler._get_tables",
        lambda: (usage_table, tenants_table, quota_table)
    )

    resp = handler(event_ok, lambda_ctx)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["message"] == "Usage recorded"
    assert "usage_id" in body

def test_missing_fields_return_400(monkeypatch, lambda_ctx):
    usage_table, tenants_table, quota_table = _mk_tables(quota_limit=1_000_000, already_used=0)
    monkeypatch.setattr(
        "services.usage.lambdas.log_usage.handler._get_tables",
        lambda: (usage_table, tenants_table, quota_table)
    )

    # Missing token_count and endpoint
    bad_event = {"body": json.dumps({"tenant_id": "tenant-1"})}
    resp = handler(bad_event, lambda_ctx)
    assert resp["statusCode"] == 400

def test_usage_within_quota_returns_200(monkeypatch, lambda_ctx):
    usage_table, tenants_table, quota_table = _mk_tables(quota_limit=5000, already_used=1000)
    monkeypatch.setattr(
        "services.usage.lambdas.log_usage.handler._get_tables",
        lambda: (usage_table, tenants_table, quota_table)
    )

    event = {"body": json.dumps({"tenant_id": "tenant-123", "token_count": 100, "endpoint": "/generate"})}
    resp = handler(event, lambda_ctx)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["message"] == "Usage recorded"

def test_usage_exceeds_quota_returns_403(monkeypatch, lambda_ctx):
    # already_used + new_tokens > quota_limit
    usage_table, tenants_table, quota_table = _mk_tables(quota_limit=5000, already_used=4900)
    monkeypatch.setattr(
        "services.usage.lambdas.log_usage.handler._get_tables",
        lambda: (usage_table, tenants_table, quota_table)
    )

    event = {"body": json.dumps({"tenant_id": "tenant-123", "token_count": 600, "endpoint": "/generate"})}
    resp = handler(event, lambda_ctx)
    assert resp["statusCode"] == 403
    assert "Quota exceeded" in json.loads(resp["body"])["message"]
