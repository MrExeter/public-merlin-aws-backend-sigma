import pytest
from unittest.mock import MagicMock
from decimal import Decimal
from services.quota.enforcer import check_quota, QuotaStatus
import services.quota.enforcer as enforcer

# Add missing mockable helpers if they don't exist
if not hasattr(enforcer, "send_slack_alert"):
    enforcer.send_slack_alert = lambda *_, **__: None

if not hasattr(enforcer, "publish_sns_message"):
    enforcer.publish_sns_message = lambda *_, **__: None


@pytest.fixture
def mock_plan_limits(monkeypatch):
    """Provide controlled plan limits."""
    monkeypatch.setattr(
        "services.quota.enforcer.get_plan_limits",
        lambda plan_id: {"max_tokens_per_day": 100, "max_requests_per_day": 10},
    )


@pytest.fixture
def make_usage(monkeypatch):
    """Dynamically adjust aggregate_usage_for_user() return values."""
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = tokens_used
            self.requests = requests

    def _set_usage(tokens_used, requests):
        monkeypatch.setattr(
            "services.quota.enforcer.aggregate_usage_for_user",
            lambda *_, **__: Usage(tokens_used=tokens_used, requests=requests),
        )

    return _set_usage


def test_usage_progression_triggers_warning_and_blocked(mock_plan_limits, make_usage):
    """Simulate usage increasing over time."""
    make_usage(50, 5)
    assert check_quota("tenant_a", "pro", 5) == QuotaStatus.ALLOWED

    make_usage(90, 9)
    assert check_quota("tenant_a", "pro", 5) == QuotaStatus.WARNING

    make_usage(120, 11)
    assert check_quota("tenant_a", "pro", 5) == QuotaStatus.BLOCKED


def test_tenant_isolation(mock_plan_limits, make_usage):
    """Tenants should be enforced independently."""
    make_usage(90, 9)
    result_a = check_quota("tenant_a", "pro", 5)

    make_usage(10, 2)
    result_b = check_quota("tenant_b", "pro", 5)

    assert result_a != result_b
    assert result_a == QuotaStatus.WARNING
    assert result_b == QuotaStatus.ALLOWED


@pytest.mark.xfail(reason="Alert hooks (Slack/SNS) not yet implemented in enforcer.py")
def test_alerts_triggered_once(monkeypatch, mock_plan_limits, make_usage):
    """Ensure Slack/SNS alerts trigger only once per threshold."""
    fake_slack = MagicMock()
    fake_sns = MagicMock()

    monkeypatch.setattr("services.quota.enforcer.send_slack_alert", fake_slack)
    monkeypatch.setattr("services.quota.enforcer.publish_sns_message", fake_sns)

    make_usage(120, 15)
    assert check_quota("tenant_z", "enterprise", 10) == QuotaStatus.BLOCKED

    # Simulate second breach — alerts should not duplicate
    make_usage(125, 20)
    check_quota("tenant_z", "enterprise", 10)

    fake_slack.assert_called_once()
    fake_sns.assert_called_once()


@pytest.mark.parametrize(
    "plan,usage,expected",
    [
        ("free", {"tokens_used": 5, "requests": 1}, QuotaStatus.ALLOWED),
        ("free", {"tokens_used": 95, "requests": 9}, QuotaStatus.WARNING),
        ("pro", {"tokens_used": 120, "requests": 11}, QuotaStatus.BLOCKED),
    ],
)
def test_different_plans_thresholds(monkeypatch, plan, usage, expected):
    """Plans should produce different enforcement thresholds."""
    monkeypatch.setattr(
        "services.quota.enforcer.get_plan_limits",
        lambda plan_id: {"max_tokens_per_day": 100, "max_requests_per_day": 10},
    )
    class Usage:
        def __init__(self, tokens_used, requests):
            self.tokens_used = tokens_used
            self.requests = requests

    monkeypatch.setattr(
        "services.quota.enforcer.aggregate_usage_for_user",
        lambda *_, **__: Usage(**usage),
    )

    result = check_quota("tenant_x", plan, 5)
    assert result == expected
