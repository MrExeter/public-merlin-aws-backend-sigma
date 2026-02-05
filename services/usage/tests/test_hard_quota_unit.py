# services/usage/tests/test_hard_quota_unit.py
import json
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
import services.usage.lambdas.log_usage.handler as mod

@pytest.fixture
def tables_ok(monkeypatch):
    usage, tenants, quota = MagicMock(), MagicMock(), MagicMock()
    tenants.get_item.return_value = {"Item": {"tenant_id": "t1", "plan_id": "pro", "subscription_status": "active"}}
    quota.get_item.return_value = {"Item": {"plan_id": "pro", "quota_limit": 1000}}
    usage.update_item.return_value = {"Attributes": {"token_total": 100}}  # allowed
    monkeypatch.setenv("HARD_QUOTA", "true")
    return usage, tenants, quota

@pytest.fixture
def tables_exceed(monkeypatch):
    usage, tenants, quota = MagicMock(), MagicMock(), MagicMock()
    tenants.get_item.return_value = {"Item": {"tenant_id": "t1", "plan_id": "pro", "subscription_status": "active"}}
    quota.get_item.return_value = {"Item": {"plan_id": "pro", "quota_limit": 100}}
    usage.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "over quota"}}, "UpdateItem"
    )
    monkeypatch.setenv("HARD_QUOTA", "true")
    return usage, tenants, quota

def test_hard_quota_allows(monkeypatch, tables_ok, lambda_ctx):
    usage, tenants, quota = tables_ok
    monkeypatch.setattr(mod, "_get_tables", lambda: (usage, tenants, quota))
    event = {"body": json.dumps({"tenant_id": "t1", "token_count": 50, "endpoint": "/x"})}
    resp = mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200
    usage.update_item.assert_called_once()

def test_hard_quota_blocks(monkeypatch, tables_exceed, lambda_ctx):
    usage, tenants, quota = tables_exceed
    monkeypatch.setattr(mod, "_get_tables", lambda: (usage, tenants, quota))
    event = {"body": json.dumps({"tenant_id": "t1", "token_count": 200, "endpoint": "/x"})}
    resp = mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 403
    usage.update_item.assert_called_once()
