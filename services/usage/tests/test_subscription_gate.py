import json
from unittest.mock import MagicMock
import services.usage.lambdas.log_usage.handler as mod

def test_subscription_inactive_returns_402(monkeypatch, lambda_ctx):
    usage_table = MagicMock()
    tenants_table = MagicMock()
    quota_table = MagicMock()

    # Tenant exists but is not active
    tenants_table.get_item.return_value = {
        "Item": {"tenant_id": "t1", "plan_id": "pro", "subscription_status": "past_due"}
    }
    # Quota present (won't be used because gate blocks first)
    quota_table.get_item.return_value = {"Item": {"plan_id": "pro", "quota_limit": 1000}}
    # Route handler to mocks
    monkeypatch.setattr(mod, "_get_tables", lambda: (usage_table, tenants_table, quota_table))

    event = {"body": json.dumps({"tenant_id": "t1", "token_count": 10, "endpoint": "/x"})}
    resp = mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 402
    usage_table.put_item.assert_not_called()
