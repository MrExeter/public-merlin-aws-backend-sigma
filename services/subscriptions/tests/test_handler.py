import json
import pytest
from decimal import Decimal
from services.subscriptions.lambdas import subscribe_user


def make_event(body: dict):
    return {"body": json.dumps(body)}

@pytest.fixture
def patch_create(monkeypatch):
    def mock_create_subscription(subscription, dynamodb=None):
        return subscription.dict()
    monkeypatch.setattr(
        "services.subscriptions.lambdas.subscribe_user.create_subscription",
        mock_create_subscription
    )
    return mock_create_subscription

def test_lambda_happy_path(monkeypatch):
    def mock_create_subscription(subscription, dynamodb=None):
        return subscription.dict()

    monkeypatch.setattr(
        "services.subscriptions.lambdas.subscribe_user.create_subscription",
        mock_create_subscription
    )

    event = make_event({
        "subscription_id": "sub123",
        "user_id": "u1",
        "plan_id": "basic",
        "paid_amount_usd": 9.99
    })
    resp = subscribe_user.handler(event, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 201
    assert body["status"] == "active"


def test_lambda_missing_fields(patch_create):
    # user_id and plan_id missing
    event = make_event({"subscription_id": "sub123"})
    resp = subscribe_user.handler(event, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 400
    assert "error" in body


def test_lambda_malformed_json():
    # body cannot be parsed as JSON
    event = {"body": "{not-json}"}
    resp = subscribe_user.handler(event, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 400
    assert "error" in body

# Stripe webhook stubs (future integration)
def test_stripe_webhook_invoice_paid(monkeypatch):
    # Simulate invoice.paid event mapping
    pass

def test_stripe_webhook_payment_failed(monkeypatch):
    # Simulate invoice.payment_failed mapping
    pass
