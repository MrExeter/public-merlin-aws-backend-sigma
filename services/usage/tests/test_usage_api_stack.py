import pytest
import time
import uuid



def test_log_usage_with_valid_token(usage_api_client, auth_client, auth_user_factory, token_factory, quota_client):
    tenant_id = "tenant-123"
    user = auth_user_factory(role="user", tenant_id=tenant_id)
    quota_client.set_quota(tenant_id, 10)   # ✅ allow usage

    token = token_factory()
    auth_client.tokens[token] = {"username": "testuser", "exp": time.time() + 60}

    resp = usage_api_client.log_usage(tenant_id, token, 5)
    assert resp["status"] == 200
    assert resp["message"] == "Usage logged"


def test_log_usage_without_token(usage_api_client):
    resp = usage_api_client.log_usage("tenant-123", None, 5)
    assert resp["status"] == 401


def test_log_usage_exceeds_quota(usage_api_client, quota_client, token_factory, auth_client):
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 1)

    token = token_factory()
    auth_client.tokens[token] = {"username": "testuser", "exp": time.time() + 60}

    resp = usage_api_client.log_usage(tenant_id, token, 5)
    assert resp["status"] == 403
    assert "QuotaExceeded" in resp["message"]


def test_aggregate_usage(usage_api_client, auth_client, token_factory, quota_client):
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 10)  # ✅ set quota so usage can be consumed

    token = token_factory()
    auth_client.tokens[token] = {"username": "testuser", "exp": time.time() + 60}

    usage_api_client.log_usage(tenant_id, token, 3)
    usage_api_client.log_usage(tenant_id, token, 2)

    resp = usage_api_client.aggregate_usage(tenant_id, token)
    assert resp["status"] == 200
    assert resp["total"] == 5
