import pytest

class FakeQuotaClient:
    """Simple in-memory mock of QuotaStack behavior for testing."""

    def __init__(self, slack=None):
        self.quotas = {}
        self.usage = {}
        self.slack = slack

    def set_quota(self, tenant_id, quota, user="admin"):
        if quota < 0:
            raise ValueError("Quota cannot be negative")
        if user != "admin":
            raise PermissionError("Unauthorized user")
        self.quotas[tenant_id] = quota
        self.usage[tenant_id] = 0

    def consume(self, tenant_id, amount):
        if tenant_id not in self.quotas:
            raise KeyError("Tenant not found")

        remaining = self.quotas[tenant_id] - self.usage[tenant_id]
        if remaining < amount:
            # NEW: publish to Slack mock
            if self.slack:
                self.slack.send_message("quota", f"QuotaExceeded for {tenant_id}")
            raise Exception("QuotaExceeded")

        self.usage[tenant_id] += amount
        return True

    def get_quota(self, tenant_id):
        return self.quotas.get(tenant_id, None)

    def remaining(self, tenant_id):
        return self.quotas[tenant_id] - self.usage[tenant_id]


@pytest.fixture
def quota_client(slack_mock):
    """Quota client that can publish alerts to Slack mock."""
    return FakeQuotaClient(slack=slack_mock)


@pytest.fixture
def unauthorized_user():
    """Fixture that represents a non-admin user."""
    return "user"
