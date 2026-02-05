# services/billing/tests/conftest.py
from types import SimpleNamespace
import pytest
import warnings
import uuid
import json
import os
from botocore.exceptions import ClientError
warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture
def lambda_ctx():
    return SimpleNamespace(
        function_name="test-fn",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-west-1:123456789012:function:test-fn",
        memory_limit_in_mb=128,
        aws_request_id="req-123",
        get_remaining_time_in_millis=lambda: 300000,
    )


# -----------------------------
# Fake Billing Client
# -----------------------------
class FakeBillingClient:
    """In-memory mock of Billing/Stripe behavior."""

    def __init__(self, slack=None, quota=None):
        self.subscriptions = {}
        self.status = {}
        self.slack = slack
        self.quota = quota
        self.processed_events = set()

    def onboard_tenant(self, tenant):
        """Simulates tenant onboarding with active subscription by default."""
        self.create_subscription(tenant["id"], "free")
        self.status[tenant["id"]] = "active"

    def create_subscription(self, tenant_id, plan):
        """Creates or replaces a subscription."""
        if not os.getenv("STRIPE_API_KEY"):
            return False

        quotas = {"free": 100, "pro": 1000, "enterprise": 10000}
        self.subscriptions[tenant_id] = {"plan": plan, "id": str(uuid.uuid4())}
        self.status[tenant_id] = "active"

        if self.quota:
            self.quota.set_quota(tenant_id, quotas.get(plan, 0))
        return True

    def update_subscription(self, tenant_id, plan):
        return self.create_subscription(tenant_id, plan)

    def simulate_payment_failure(self, tenant_id):
        self.status[tenant_id] = "past_due"
        if self.slack:
            self.slack.send_message("billing", f"Failed payment for {tenant_id}")

    def simulate_expired_card(self, tenant_id):
        self.status[tenant_id] = "payment_failed"
        if self.slack:
            self.slack.send_message("billing", f"Expired card for {tenant_id}")

    def get_status(self, tenant_id):
        return self.status.get(tenant_id, "no_subscription")

    def get_subscriptions(self, tenant_id):
        return [self.subscriptions[tenant_id]] if tenant_id in self.subscriptions else []

    def process_webhook(self, event):
        """Processes webhook events and validates signature."""
        if not event.get("valid_signature"):
            return False
        if event["id"] in self.processed_events:
            return False
        self.processed_events.add(event["id"])
        return True


# -----------------------------
# Fixtures
# -----------------------------

@pytest.fixture
def billing_client(slack_mock, quota_client):
    """Provides a fake Billing client with Slack + Quota integration."""
    # Default Stripe key for tests
    os.environ.setdefault("STRIPE_API_KEY", "sk_test_dummy")
    return FakeBillingClient(slack=slack_mock, quota=quota_client)


@pytest.fixture
def tenant_factory():
    """Factory for generating fake tenants."""
    def _create_tenant(name="test-tenant"):
        return {"id": str(uuid.uuid4()), "name": name}
    return _create_tenant


@pytest.fixture
def webhook_event_factory():
    """Factory for generating realistic Stripe-like webhook events."""
    def _create_event(valid_signature=True, event_type="invoice.payment_failed"):
        payload = {
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "data": {"object": {"id": f"sub_{uuid.uuid4().hex[:8]}"}}
        }

        headers = {"Stripe-Signature": "test-signature"} if valid_signature else {}
        return {
            "body": json.dumps(payload),  # must be a JSON string
            "headers": headers
        }

    return _create_event


# -----------------------------
# IAM Role Checker (shared)
# -----------------------------
@pytest.fixture(scope="function")
def iam_role_checker():
    """Fake IAM role checker until wired into CDK output."""
    def _check(role_name):
        # Return a safe, scoped policy for now
        return [
            {
                "Action": "cognito:InitiateAuth",
                "Resource": "arn:aws:cognito-idp:us-west-1:123456789012:userpool/mock"
            }
        ]
    return _check


class FakeEventsTable:
    """In-memory fake DynamoDB table for webhook idempotency tests."""
    def __init__(self):
        self.items = set()
    def put_item(self, Item=None, **kwargs):
        event_id = Item.get("id") if Item else None
        if event_id in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "PutItem"
            )
        self.items.add(event_id)

@pytest.fixture(scope="function")
def fake_events_table(monkeypatch):
    table = FakeEventsTable()
    monkeypatch.setattr(
        "services.billing.stripe_webhook_lambda._get_events_table",
        lambda: table
    )
    return table
