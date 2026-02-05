# services/billing/tests/test_subscribe_lambda.py
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# ✅ Ensure env vars exist before importing the Lambda
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_fake"
os.environ["SUBSCRIPTIONS_TABLE"] = "SubscriptionsTable"
os.environ["STRIPE_PRICE_ID"] = "premium-plan-dev"

from services.billing.lambdas import subscribe_lambda


def make_event(body: dict):
    """Helper to build API Gateway-like event."""
    return {"body": json.dumps(body)}


# ✅ Happy path
@patch("services.billing.lambdas.subscribe_lambda.stripe.Customer.create")
@patch("services.billing.lambdas.subscribe_lambda.stripe.Subscription.create")
@patch("services.billing.lambdas.subscribe_lambda.subscriptions_table")
def test_subscribe_happy_path(mock_table, mock_sub_create, mock_cust_create):
    mock_cust_create.return_value = MagicMock(id="cust_123")
    mock_sub_create.return_value = MagicMock(id="sub_456", status="active")

    event = make_event({"email": "user@example.com", "tenant_id": "tenant_1"})
    resp = subscribe_lambda.handler(event, {})

    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["customer_id"] == "cust_123"
    assert body["subscription_id"] == "sub_456"
    assert body["status"] == "active"
    mock_table.put_item.assert_called_once()


# ❌ Invalid input (bad JSON)
def test_subscribe_invalid_input():
    event = {"body": "not-a-json"}
    resp = subscribe_lambda.handler(event, {})
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "error" in body


# ❌ Invalid input (missing fields)
def test_subscribe_missing_fields():
    event = make_event({"email": "user@example.com"})  # missing tenant_id
    resp = subscribe_lambda.handler(event, {})
    assert resp["statusCode"] == 400


# ❌ Stripe failure path
@patch("services.billing.lambdas.subscribe_lambda.stripe.Customer.create", side_effect=Exception("Stripe down"))
def test_subscribe_stripe_failure(_):
    event = make_event({"email": "user@example.com", "tenant_id": "tenant_1"})
    resp = subscribe_lambda.handler(event, {})
    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "Stripe down" in body["error"]


# ❌ DynamoDB failure path
@patch("services.billing.lambdas.subscribe_lambda.stripe.Customer.create")
@patch("services.billing.lambdas.subscribe_lambda.stripe.Subscription.create")
@patch("services.billing.lambdas.subscribe_lambda.subscriptions_table.put_item", side_effect=Exception("DDB error"))
def test_subscribe_dynamodb_failure(_, mock_sub_create, mock_cust_create):
    mock_cust_create.return_value = MagicMock(id="cust_123")
    mock_sub_create.return_value = MagicMock(id="sub_456", status="active")
    event = make_event({"email": "user@example.com", "tenant_id": "tenant_1"})
    resp = subscribe_lambda.handler(event, {})
    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert "DDB error" in body["error"]
