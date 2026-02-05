import pytest

import services.usage.tests.conftest
# --- Sad-path tests ---

def test_quota_exceeded_raises_error(quota_client):
    """Tenant exceeds assigned quota → should raise QuotaExceeded error."""
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 100)
    quota_client.consume(tenant_id, 100)

    with pytest.raises(Exception) as exc:
        quota_client.consume(tenant_id, 1)
    assert "QuotaExceeded" in str(exc.value)


def test_quota_exhausted_exact_limit(quota_client):
    """Consuming exactly the quota is allowed, one more request should fail."""
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 10)

    for _ in range(10):
        quota_client.consume(tenant_id, 1)

    with pytest.raises(Exception):
        quota_client.consume(tenant_id, 1)


def test_unauthorized_quota_change(quota_client, unauthorized_user):
    """Unauthorized user attempts to modify quota → should fail."""
    tenant_id = "tenant-123"
    with pytest.raises(PermissionError):
        quota_client.set_quota(tenant_id, 200, user=unauthorized_user)


# --- Edge-case tests ---

def test_quota_zero_blocks_all_requests(quota_client):
    """Quota set to 0 → all requests blocked immediately."""
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 0)

    with pytest.raises(Exception):
        quota_client.consume(tenant_id, 1)


def test_quota_negative_invalid(quota_client):
    """Negative quota values should be rejected at config time."""
    tenant_id = "tenant-123"
    with pytest.raises(ValueError):
        quota_client.set_quota(tenant_id, -10)


def test_quota_large_number(quota_client):
    """Very large quota values should be accepted without overflow."""
    tenant_id = "tenant-123"
    large_quota = 10 ** 9
    quota_client.set_quota(tenant_id, large_quota)
    assert quota_client.get_quota(tenant_id) == large_quota


# --- Integration tests ---

def test_quota_breach_triggers_slack_alert(quota_client, usage_client, slack_mock):
    """Quota breach should publish an alert to Slack quota channel."""
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 5)

    for _ in range(6):  # exceed quota
        try:
            quota_client.consume(tenant_id, 1)
        except Exception:
            pass

    alerts = slack_mock.get_messages(channel="quota")
    assert any("QuotaExceeded" in msg for msg in alerts)


def test_usage_stack_reports_to_quota(quota_client, usage_client):
    """UsageStack should feed into QuotaStack correctly."""
    tenant_id = "tenant-123"
    quota_client.set_quota(tenant_id, 3)

    for _ in range(2):
        usage_client.record_usage(tenant_id, 1)

    remaining = quota_client.remaining(tenant_id)
    assert remaining == 1
