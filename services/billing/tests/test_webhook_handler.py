import os
import sys
import json

# Add parent folder (services/billing) to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.billing import stripe_webhook_lambda as handler_mod

import pytest
from unittest.mock import patch
import stripe


# Compatibility shim for SignatureVerificationError
try:
    # New Stripe SDK (>=6.x)
    SignatureVerificationError = stripe.SignatureVerificationError
except AttributeError:
    try:
        # Old Stripe SDK (<6.x)
        from stripe.error import SignatureVerificationError  # type: ignore
    except ImportError:
        SignatureVerificationError = getattr(stripe, "SignatureVerificationError", None)


@pytest.fixture
def stripe_event():
    return {
        "id": "evt_123",
        "type": "customer.subscription.updated",
        "created": 1699999999,
        "data": {
            "object": {
                "customer": "cus_abc123",
                "status": "active",
                "items": {
                    "data": [
                        {
                            "plan": {
                                "id": "premium-plan-dev"
                            }
                        }
                    ]
                }
            }
        }
    }


@patch("stripe.Webhook.construct_event", side_effect=ValueError("Bad payload"))
def test_bad_event_returns_400(mock_construct, lambda_ctx):
    event = {
        "headers": {
            "stripe-signature": "bad",
        },
        "body": "{}"
    }

    # resp = handler_mod.handler(event, None)
    resp = handler_mod.handler(event, lambda_ctx)
    print(f"The Response was {resp}!!!!!!!!!!!!!!!!!!")
    assert resp["statusCode"] == 400


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_invoice_paid_event(mock_boto, mock_construct, lambda_ctx):
    # Mock DynamoDB put_item so no real table is needed
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_paid",
        "type": "invoice.paid",
        "created": 1700000000,
        "data": {"object": {"customer": "cus_abc", "status": "active",
                            "items": {"data": [{"plan": {"id": "basic-plan"}}]}}},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_invoice_payment_failed_event(mock_boto, mock_construct, lambda_ctx):
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_failed",
        "type": "invoice.payment_failed",
        "created": 1700000001,
        "data": {"object": {"customer": "cus_def", "status": "past_due",
                            "items": {"data": [{"plan": {"id": "pro-plan"}}]}}},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_subscription_deleted_event(mock_boto, mock_construct, lambda_ctx):
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_deleted",
        "type": "customer.subscription.deleted",
        "created": 1700000002,
        "data": {"object": {"customer": "cus_xyz", "status": "canceled",
                            "items": {"data": [{"plan": {"id": "enterprise-plan"}}]}}},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_subscription_upgrade_event(mock_boto, mock_construct, lambda_ctx):
    # Upgrade: basic → pro
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_upgrade",
        "type": "customer.subscription.updated",
        "created": 1700000003,
        "data": {"object": {
            "customer": "cus_upgrade",
            "status": "active",
            "items": {"data": [{"plan": {"id": "pro-plan"}}]}
        }},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_subscription_downgrade_event(mock_boto, mock_construct, lambda_ctx):
    # Downgrade: pro → basic
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_downgrade",
        "type": "customer.subscription.updated",
        "created": 1700000004,
        "data": {"object": {
            "customer": "cus_downgrade",
            "status": "active",
            "items": {"data": [{"plan": {"id": "basic-plan"}}]}
        }},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_trial_to_paid_event(mock_boto, mock_construct, lambda_ctx):
    # Trial ends → first invoice.paid
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_trial_paid",
        "type": "invoice.paid",
        "created": 1700000005,
        "data": {"object": {
            "customer": "cus_trial",
            "status": "active",
            "items": {"data": [{"plan": {"id": "basic-plan"}}]}
        }},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_event_idempotency(mock_boto, mock_construct, lambda_ctx):
    # Same event sent twice → should still succeed, no duplicate error
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    event_payload = {
        "id": "evt_idempotent",
        "type": "customer.subscription.updated",
        "created": 1700000006,
        "data": {"object": {
            "customer": "cus_idempotent",
            "status": "active",
            "items": {"data": [{"plan": {"id": "basic-plan"}}]}
        }},
    }
    mock_construct.return_value = event_payload

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    # Send event twice
    resp1 = handler_mod.handler(event, lambda_ctx)
    resp2 = handler_mod.handler(event, lambda_ctx)

    assert resp1["statusCode"] == 200
    assert resp2["statusCode"] == 200


@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_payment_failed_then_paid(mock_boto, mock_construct, lambda_ctx):
    # Out-of-order: fail → success
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}

    # First failure
    fail_payload = {
        "id": "evt_fail_first",
        "type": "invoice.payment_failed",
        "created": 1700000007,
        "data": {"object": {
            "customer": "cus_retry",
            "status": "past_due",
            "items": {"data": [{"plan": {"id": "pro-plan"}}]}
        }},
    }
    mock_construct.return_value = fail_payload
    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp1 = handler_mod.handler(event, lambda_ctx)
    assert resp1["statusCode"] == 200

    # Then success
    success_payload = {
        "id": "evt_paid_retry",
        "type": "invoice.paid",
        "created": 1700000008,
        "data": {"object": {
            "customer": "cus_retry",
            "status": "active",
            "items": {"data": [{"plan": {"id": "pro-plan"}}]}
        }},
    }
    mock_construct.return_value = success_payload
    resp2 = handler_mod.handler(event, lambda_ctx)
    assert resp2["statusCode"] == 200


def test_missing_env_vars(monkeypatch, lambda_ctx):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    with pytest.raises(RuntimeError):
        handler_mod.handler(event, lambda_ctx)


def test_missing_signature_header(lambda_ctx):
    event = {"headers": {}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 400


@patch("services.billing.stripe_webhook_lambda._get_table")
@patch("services.billing.stripe_webhook_lambda._get_events_table")
@patch("services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event")
def test_dynamodb_put_item_failure(mock_construct, mock_get_events, mock_get_table, lambda_ctx):
    # Construct a valid subscription update event
    mock_construct.return_value = {
        "id": "evt_ddb_fail",
        "type": "customer.subscription.updated",
        "created": 1700000010,
        "data": {"object": {
            "customer": "cus_fail",
            "status": "active",
            "items": {"data": [{"plan": {"id": "basic-plan"}}]}
        }},
    }

    # Events table put succeeds (idempotency marker)
    mock_events_table = mock_get_events.return_value
    mock_events_table.put_item.return_value = {}

    # Subscriptions table put fails
    mock_subs_table = mock_get_table.return_value
    mock_subs_table.put_item.side_effect = Exception("DDB error")

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 500
    assert "Error saving subscription" in resp["body"]



@patch("stripe.Webhook.construct_event")
@patch("boto3.resource")
def test_unsupported_event_type(mock_boto, mock_construct, lambda_ctx):
    mock_table = mock_boto.return_value.Table.return_value
    mock_table.put_item.return_value = {}
    mock_construct.return_value = {
        "id": "evt_unhandled",
        "type": "payout.created",
        "created": 1700000011,
        "data": {"object": {}},
    }
    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 200


def test_missing_body(lambda_ctx):
    """Event without a body → should 400 (malformed)."""
    event = {"headers": {"stripe-signature": "sig"}}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 400
    assert "Malformed event" in resp["body"]


def test_body_not_string(lambda_ctx):
    """Body is not a string → signature verification fails → 400."""
    event = {"headers": {"stripe-signature": "sig"}, "body": {"not": "a string"}}
    resp = handler_mod.handler(event, lambda_ctx)
    assert resp["statusCode"] == 400
    assert "Invalid signature" in resp["body"]


@patch("services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event")
def test_event_missing_id(mock_construct, lambda_ctx):
    """Constructed event missing 'id' field → should 400."""
    mock_construct.return_value = {"type": "invoice.paid"}  # no "id"

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 400
    assert "Missing event id" in resp["body"]


@patch("services.billing.stripe_webhook_lambda._get_events_table")
@patch("services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event")
def test_unhandled_event_type_returns_200_ok(mock_construct, mock_get_events, lambda_ctx):
    # Event has id + an unsupported type -> handler should no-op and return 200
    mock_construct.return_value = {
        "id": "evt_unhandled",
        "type": "payout.created",  # unsupported
        "created": 1700000011,
        "data": {"object": {}},
    }

    # Avoid real DDB
    mock_get_events.return_value.put_item.return_value = {}

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    resp = handler_mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 200
    assert '"message": "ok"' in resp["body"]



"""
# When we go to production, we want to test against real DynamoDB tables.
# 🔒 Integration Fixture (Phase III hardening)

import boto3
from moto import mock_aws
import pytest

@pytest.fixture
def dynamodb_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")

        # SubscriptionsTable
        client.create_table(
            TableName="SubscriptionsTable",
            KeySchema=[{"AttributeName": "subscription_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "subscription_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # StripeEvents table
        client.create_table(
            TableName="StripeEvents",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield boto3.resource("dynamodb", region_name="us-east-1")


def test_invoice_payment_failed_sets_past_due_integration(dynamodb_tables, lambda_ctx):
    # Example: send a payment_failed event, then assert the SubscriptionsTable was updated
    from unittest.mock import patch
    from services.billing import stripe_webhook_lambda as handler_mod

    event_payload = {
        "id": "evt_failed",
        "type": "invoice.payment_failed",
        "created": 1700000001,
        "data": {"object": {"customer": "cus_def", "status": "past_due",
                            "items": {"data": [{"plan": {"id": "pro-plan"}}]}}},
    }

    with patch("stripe.Webhook.construct_event", return_value=event_payload):
        event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
        resp = handler_mod.handler(event, lambda_ctx)
        assert resp["statusCode"] == 200

    table = dynamodb_tables.Table("SubscriptionsTable")
    items = table.scan().get("Items", [])
    assert any(item.get("status") == "past_due" for item in items)
"""

