# services/conftest.py
import types
import uuid

import pytest


@pytest.fixture
def lambda_context():
    """Fake AWS Lambda context for Powertools."""
    ctx = types.SimpleNamespace()
    ctx.function_name = "test-function"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:local:test"
    ctx.aws_request_id = "test-request-id"
    return ctx


# -----------------------------
# Slack Mock
# -----------------------------
class SlackMock:
    """Captures messages 'sent' to Slack for assertion in tests."""

    def __init__(self):
        self.messages = {}

    def send_message(self, channel, text):
        if channel not in self.messages:
            self.messages[channel] = []
        self.messages[channel].append(text)

    def get_messages(self, channel):
        return self.messages.get(channel, [])


@pytest.fixture(scope="function")
def slack_mock():
    """Provides a fake Slack client for tests."""
    return SlackMock()


# -----------------------------
# Auth / Cognito User Factory
# -----------------------------
@pytest.fixture(scope="function")
def auth_user_factory():
    """Factory that generates fake user objects for tests."""

    def _create_user(role="user", tenant_id=None):
        return {
            "id": str(uuid.uuid4()),
            "role": role,
            "tenant_id": tenant_id or f"tenant-{uuid.uuid4()}",
        }

    return _create_user


# -----------------------------
# Quota Client (shared)
# -----------------------------
class FakeQuotaClient:
    """In-memory mock of QuotaStack behavior."""

    def __init__(self):
        self.quotas = {}
        self.usage = {}

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
            raise Exception("QuotaExceeded")

        self.usage[tenant_id] += amount
        return True

    def remaining(self, tenant_id):
        return self.quotas[tenant_id] - self.usage[tenant_id]


@pytest.fixture(scope="function")
def quota_client():
    """Provides a fake QuotaStack client for tests."""
    return FakeQuotaClient()


# -----------------------------
# Usage Client (shared)
# -----------------------------
class FakeUsageClient:
    """In-memory mock of UsageStack behavior."""

    def __init__(self, quota_client=None):
        self.records = {}
        self.quota_client = quota_client

    def record_usage(self, tenant_id, amount):
        if tenant_id not in self.records:
            self.records[tenant_id] = 0
        self.records[tenant_id] += amount

        if self.quota_client:
            self.quota_client.consume(tenant_id, amount)

    def get_usage(self, tenant_id):
        return self.records.get(tenant_id, 0)


@pytest.fixture(scope="function")
def usage_client(quota_client):
    """Provides a fake Usage client linked to Quota."""
    return FakeUsageClient(quota_client)
