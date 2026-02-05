import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from services.quota.enforcer import check_quota, write_quota_state, QuotaStatus


@pytest.fixture
def mock_plan_limits(monkeypatch):
    """Mock get_plan_limits to control max limits."""
    monkeypatch.setattr("services.quota.enforcer.get_plan_limits", lambda plan_id: {
        "max_tokens_per_day": 100,
        "max_requests_per_day": 10
    })


@pytest.fixture
def mock_usage(monkeypatch):
    """Mock aggregate_usage_for_user to simulate token/request usage."""
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = tokens_used
            self.requests = requests
    def _mock_agg(user_id, date, dynamodb=None):
        return Usage(tokens_used=50, requests=5)
    monkeypatch.setattr("services.quota.enforcer.aggregate_usage_for_user", _mock_agg)


def test_quota_allowed(monkeypatch, mock_plan_limits, mock_usage):
    result = check_quota("user1", "pro", 10)
    assert result == QuotaStatus.ALLOWED


def test_quota_warning(monkeypatch, mock_plan_limits):
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = 85
            self.requests = 9
    monkeypatch.setattr("services.quota.enforcer.aggregate_usage_for_user", lambda *_, **__: Usage(85, 9))
    result = check_quota("user1", "pro", 1)
    assert result == QuotaStatus.WARNING


def test_quota_blocked(monkeypatch, mock_plan_limits):
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = 95
            self.requests = 10
    monkeypatch.setattr("services.quota.enforcer.aggregate_usage_for_user", lambda *_, **__: Usage(95, 10))
    result = check_quota("user1", "pro", 10)
    assert result == QuotaStatus.BLOCKED


def test_quota_edge_near_limit(monkeypatch, mock_plan_limits):
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = 79
            self.requests = 8
    monkeypatch.setattr("services.quota.enforcer.aggregate_usage_for_user", lambda *_, **__: Usage(79, 8))
    result = check_quota("tenantX", "enterprise", 1)
    assert result in [QuotaStatus.ALLOWED, QuotaStatus.WARNING]


def test_write_quota_state(monkeypatch):
    """Validate DynamoDB write structure and values."""
    mock_put = MagicMock()
    mock_tbl = MagicMock()
    mock_tbl.put_item = mock_put
    monkeypatch.setattr("services.quota.enforcer._quota_tbl", mock_tbl)

    write_quota_state(tenant_id="t1", period_label="2025-10", plan_cap=100, used_tokens=50)
    args, kwargs = mock_put.call_args
    item = kwargs["Item"]
    assert item["limit"] == Decimal("100")
    assert item["used_pct"] == Decimal("50")
    assert "tenant_id" in item
    assert "updated_at" in item
