# services/usage/tests/test_idempotency.py
import json
from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

import services.usage.lambdas.log_usage.handler as mod


def test_duplicate_request_is_idempotent(monkeypatch, lambda_ctx):
    # Mocks for the three tables the handler uses
    usage_table = MagicMock()
    tenants_table = MagicMock()
    quota_table = MagicMock()

    # Subscription + plan OK
    tenants_table.get_item.return_value = {"Item": {"tenant_id": "t1", "plan_id": "pro", "subscription_status": "active"}}
    quota_table.get_item.return_value = {"Item": {"plan_id": "pro", "quota_limit": 1000000}}

    # Soft-quota path (default) will query usage_table; return empty to allow
    usage_table.query.return_value = {"Items": []}

    # Simulate sequence of put_item calls on the *same* usage_table:
    # 1) first request: marker write OK
    # 2) first request: usage row write OK
    # 3) second request: marker write raises ConditionalCheckFailedException (duplicate)
    usage_table.put_item.side_effect = [
        {},  # marker #1
        {},  # usage row #1
        ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "dup"}}, "PutItem"),  # marker #2
    ]

    # Route handler to our mocks
    monkeypatch.setattr(mod, "_get_tables", lambda: (usage_table, tenants_table, quota_table))

    # Fixed event with the same requestId so the computed usage_id is identical
    event = {
        "requestContext": {"requestId": "req-123"},
        "body": json.dumps({"tenant_id": "t1", "token_count": 5, "endpoint": "/x"})
    }

    r1 = mod.handler(event, lambda_ctx)
    r2 = mod.handler(event, lambda_ctx)

    assert r1["statusCode"] == 200
    assert r2["statusCode"] == 200

    # We expect exactly 3 put_item calls: marker1, usage1, marker2(duplicate -> stops)
    assert usage_table.put_item.call_count == 3

    # (Optional) sanity: third call was the marker (timestamp starts with 'IDEMP#')
    third_kwargs = usage_table.put_item.call_args_list[2].kwargs
    assert third_kwargs["Item"]["timestamp"].startswith("IDEMP#")
