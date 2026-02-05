# services/usage/tests/usage_test_patch_phase4.py
# Phase IV alignment tests for the refactored Usage log handler.
# These tests DO NOT replace your existing ones yet; they coexist to validate
# the new deterministic response contract and metrics emission.

import json
from unittest.mock import patch, MagicMock
import types
import pytest
import botocore.exceptions as botoerr

import services.usage.lambdas.log_usage.handler as H


# --- Local fixtures ---------------------------------------------------------

@pytest.fixture
def lambda_context():
    """Fake AWS Lambda context so Powertools decorators work in tests."""
    ctx = types.SimpleNamespace()
    ctx.function_name = "usage-log-test"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:local:000000000000:function:usage-log-test"
    ctx.aws_request_id = "req-123"
    return ctx


@pytest.fixture
def good_event():
    """Baseline good event body."""
    return {
        "body": json.dumps({
            "tenant_id": "tenant-1",
            "token_count": 123,
            "endpoint": "/api/gpt"
        })
    }


# --- Tests: payload validation ----------------------------------------------

def test_bad_payload_json(lambda_context):
    event = {"body": "{bad json"}
    resp = H.handler(event, lambda_context)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"] == "Bad payload"


def test_missing_required_fields(lambda_context):
    event = {"body": json.dumps({"token_count": 10})}  # tenant_id missing
    resp = H.handler(event, lambda_context)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"] == "Bad payload"


# --- Tests: subscription gate (402) -----------------------------------------

def test_subscription_inactive_returns_402(lambda_context, good_event):
    with patch.object(H, "_is_subscription_active", return_value=False):
        resp = H.handler(good_event, lambda_context)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"])
    assert body["message"] == "Subscription inactive"


# --- Tests: quota enforcement (403 vs pass) ---------------------------------

def test_quota_exceeded_returns_403(lambda_context, good_event):
    with patch.object(H, "_is_subscription_active", return_value=True), \
         patch.object(H, "_try_consume_quota", return_value=False):
        resp = H.handler(good_event, lambda_context)

    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert body["message"] == "Quota exceeded"


def test_quota_allows_then_records_usage_and_emits_metric(lambda_context, good_event):
    usage_tbl = MagicMock()
    tenants_tbl = MagicMock()
    quota_tbl = MagicMock()
    with patch.object(H, "_is_subscription_active", return_value=True), \
         patch.object(H, "_try_consume_quota", return_value=True), \
         patch.object(H, "_get_tables", return_value=(usage_tbl, tenants_tbl, quota_tbl)), \
         patch.object(H.metrics, "add_metric") as mock_metric:
        resp = H.handler(good_event, lambda_context)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["message"] == "Usage recorded"
    assert body["tenant_id"] == "tenant-1"
    # Ensure we wrote one item and emitted one metric
    usage_tbl.put_item.assert_called_once()
    mock_metric.assert_called_once()


# --- Tests: idempotency (duplicate) -----------------------------------------

def test_idempotent_duplicate_returns_200_and_does_not_raise(lambda_context, good_event):
    """Simulate ConditionalCheckFailedException -> treated as duplicate, success 200."""
    usage_tbl = MagicMock()
    tenants_tbl = MagicMock()
    quota_tbl = MagicMock()

    dup = botoerr.ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
        "PutItem"
    )
    usage_tbl.put_item.side_effect = dup

    with patch.object(H, "_is_subscription_active", return_value=True), \
         patch.object(H, "_try_consume_quota", return_value=True), \
         patch.object(H, "_get_tables", return_value=(usage_tbl, tenants_tbl, quota_tbl)), \
         patch.object(H.metrics, "add_metric") as mock_metric:
        resp = H.handler(good_event, lambda_context)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "Duplicate" in body["message"] or "duplicate" in body["message"].lower()
    # For duplicates, we should NOT count a new usage metric; assert not called.
    mock_metric.assert_not_called()


# --- Tests: write failures (500) --------------------------------------------

def test_generic_dynamodb_failure_returns_500(lambda_context, good_event):
    usage_tbl = MagicMock()
    tenants_tbl = MagicMock()
    quota_tbl = MagicMock()
    usage_tbl.put_item.side_effect = Exception("DB down")

    with patch.object(H, "_is_subscription_active", return_value=True), \
         patch.object(H, "_try_consume_quota", return_value=True), \
         patch.object(H, "_get_tables", return_value=(usage_tbl, tenants_tbl, quota_tbl)), \
         patch.object(H.metrics, "add_metric") as mock_metric:
        resp = H.handler(good_event, lambda_context)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert body["message"] == "Internal write failure"
    mock_metric.assert_not_called()


# --- Tests: environment/table wiring (sanity) --------------------------------

def test_get_tables_uses_env_defaults(monkeypatch):
    # Ensure no crash when resolving tables; we only validate that calls happen.
    # We patch boto3.resource to avoid real AWS.
    fake_ddb = MagicMock()
    fake_ddb.Table.return_value = MagicMock()
    with patch("services.usage.lambdas.log_usage.handler.boto3.resource", return_value=fake_ddb):
        u, t, q = H._get_tables()
    assert u is not None and t is not None and q is not None
    assert fake_ddb.Table.call_count == 3
