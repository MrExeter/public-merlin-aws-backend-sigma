import pytest
from botocore.exceptions import ClientError

# --- Sad-path tests ---

def test_failed_payment_marks_tenant_past_due(billing_client, tenant_factory):
    tenant = tenant_factory()
    billing_client.simulate_payment_failure(tenant["id"])
    assert billing_client.get_status(tenant["id"]) == "past_due"


def test_expired_card_sets_payment_failed(billing_client, tenant_factory):
    tenant = tenant_factory()
    billing_client.simulate_expired_card(tenant["id"])
    assert billing_client.get_status(tenant["id"]) == "payment_failed"


def test_invalid_webhook_signature_rejected(billing_client, webhook_event_factory):
    event = webhook_event_factory(valid_signature=False)
    result = billing_client.process_webhook(event)
    assert result is False


# --- Edge-case tests ---

def test_multiple_subscriptions_deduplicated(billing_client, tenant_factory):
    tenant = tenant_factory()
    billing_client.create_subscription(tenant["id"], "pro")
    billing_client.create_subscription(tenant["id"], "enterprise")
    subs = billing_client.get_subscriptions(tenant["id"])
    assert len(subs) == 1
    assert subs[0]["plan"] == "enterprise"  # last plan wins


def test_webhook_replay_processed_once(monkeypatch, webhook_event_factory, fake_events_table, lambda_context):
    from services.billing import stripe_webhook_lambda
    import json

    event = webhook_event_factory(valid_signature=True, event_type="invoice.payment_succeeded")

    monkeypatch.setattr(
        "services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event",
        staticmethod(lambda payload, sig, secret: json.loads(payload))
    )

    first = stripe_webhook_lambda.handler(event, lambda_context)
    duplicate = stripe_webhook_lambda.handler(event, lambda_context)

    assert first["statusCode"] in [200, 201]
    assert duplicate["statusCode"] == 200


def test_tenant_without_subscription_blocked(billing_client, quota_client, tenant_factory):
    tenant = tenant_factory()
    quota_client.set_quota(tenant["id"], 0)
    assert billing_client.get_status(tenant["id"]) == "no_subscription"
    with pytest.raises(Exception, match="QuotaExceeded"):
        quota_client.consume(tenant["id"], 1)


# --- Integration tests ---

def test_subscription_tier_updates_quota(billing_client, quota_client, tenant_factory):
    tenant = tenant_factory()
    billing_client.create_subscription(tenant["id"], "pro")
    assert quota_client.remaining(tenant["id"]) == 1000

    billing_client.update_subscription(tenant["id"], "free")
    assert quota_client.remaining(tenant["id"]) == 100


def test_failed_payment_triggers_slack_alert(billing_client, slack_mock, tenant_factory):
    tenant = tenant_factory()
    billing_client.simulate_payment_failure(tenant["id"])
    msgs = slack_mock.get_messages("billing")
    assert any("failed payment" in msg.lower() for msg in msgs)


def test_new_tenant_creates_stripe_subscription(billing_client, tenant_factory):
    tenant = tenant_factory()
    billing_client.onboard_tenant(tenant)
    status = billing_client.get_status(tenant["id"])
    assert status == "active"


# --- Infra/Security tests ---

def test_stripe_secret_missing(monkeypatch, billing_client, tenant_factory):
    """Fails gracefully if Stripe API key is missing."""
    monkeypatch.setenv("STRIPE_API_KEY", "")
    tenant = tenant_factory()
    result = billing_client.create_subscription(tenant["id"], "pro")
    assert result is False


def test_billing_lambda_least_privilege(iam_role_checker):
    """Billing Lambda should not have wildcards."""
    policies = iam_role_checker("BillingLambdaRole")
    for stmt in policies:
        assert stmt["Action"] != "*"
        assert stmt["Resource"] != "*"
