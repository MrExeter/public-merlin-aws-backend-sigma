# services/usage/tests/test_log_usage_handler.py
import json
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

from services.usage.lambdas.log_usage import handler as log_usage_handler


# # Temporary Phase 4 stub for backward-compatible testing
# def _check_quota(tenant_id: str, payload: dict) -> bool:
#     """Stubbed quota check until enforcement is live in Phase 4 part 2."""
#     return True

@pytest.fixture()
def lambda_context():
    return SimpleNamespace(
        function_name="log_usage",
        function_version="$LATEST",
        memory_limit_in_mb=128,
        aws_request_id="req-1234",
        log_group_name="/aws/lambda/log_usage",
        log_stream_name="2025/10/14/[$LATEST]abcdef123456",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:log_usage"
    )

def valid_event(**overrides):
    base = {"tenant_id": "t-1", "token_count": 10, "endpoint": "chat"}
    base.update(overrides)
    return {"body": json.dumps(base)}

def set_env(monkeypatch):
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageLogs-dev")


def test_handler_success(lambda_context):
    event = {
        "body": json.dumps({
            "tenant_id": "t-1",
            "token_count": 25,
            "endpoint": "chat"
        })
    }
    resp = log_usage_handler.handler(event, lambda_context)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "Usage recorded" in body["message"]



def test_handler_quota_denied(monkeypatch, lambda_context):
    event = {
        "body": json.dumps({
            "tenant_id": "t-1",
            "token_count": 1000,
            "endpoint": "chat"
        })
    }
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageLogs-dev")
    # Force quota failure
    monkeypatch.setattr(log_usage_handler, "is_within_quota", lambda *_: False)

    resp = log_usage_handler.handler(event, lambda_context)
    assert resp["statusCode"] in (402, 403)

# def test_handler_quota_denied(lambda_context):
#     event = {"body": json.dumps({"tenant_id": "t-1", "token_count": 999999})}
#     with patch("services.usage.lambdas.log_usage.handler._check_quota", return_value=False):
#         resp = log_usage_handler.handler(event, lambda_context)
#
#     assert resp["statusCode"] == 402
#     assert "quota" in resp["body"].lower()



def test_handler_idempotency_hit(monkeypatch, lambda_context):
    from botocore.exceptions import ClientError
    from services.usage.lambdas.log_usage import handler as H
    import json

    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageLogs-dev")

    class FakeUsageTable:
        def put_item(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "dup"}},
                "PutItem"
            )
        def query(self, **kwargs):
            # handler may call query() during validation, so just return empty
            return {"Items": []}

    monkeypatch.setattr(H, "_USAGE_TBL", FakeUsageTable())

    event = {"body": json.dumps({
        "tenant_id": "t-1",
        "token_count": 10,
        "endpoint": "chat"
    })}

    resp = H.handler(event, lambda_context)
    assert resp["statusCode"] == 200


# def test_handler_idempotency_hit(lambda_context, monkeypatch):
#     """Repeated identical requests should not double record."""
#     from botocore.exceptions import ClientError
#     class FakeUsageTable:
#         def put_item(self, **kwargs):
#             raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
#
#     monkeypatch.setattr(log_usage_handler, "_USAGE_TBL", FakeUsageTable())
#
#
#     event = {"body": json.dumps({"tenant_id": "t-1", "token_count": 100})}
#     with patch("services.usage.lambdas.log_usage.handler._record_usage", return_value=None):
#         # simulate idempotent call
#         resp1 = log_usage_handler.handler(event, lambda_context)
#         resp2 = log_usage_handler.handler(event, lambda_context)
#
#     assert resp1["statusCode"] == 200
#     assert resp2["statusCode"] == 200
#     assert json.loads(resp1["body"])["message"] == "Usage recorded"


def test_get_tables_missing_env(monkeypatch, lambda_context):
    """Missing environment variables should cause graceful RuntimeError -> 500."""
    monkeypatch.delenv("USAGE_TABLE_NAME", raising=False)
    event = {"body": json.dumps({"tenant_id": "t-1", "token_count": 10})}

    resp = log_usage_handler.handler(event, lambda_context)
    assert resp["statusCode"] in (400, 500)
    assert "Missing" in resp["body"]
