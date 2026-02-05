# services/billing/tests/test_webhook_signature.py
from unittest.mock import patch
import pytest
import stripe
from unittest.mock import patch

import services.billing.stripe_webhook_lambda as mod

# 🔒 Compatibility shim for SignatureVerificationError
try:
    SignatureVerificationError = stripe.SignatureVerificationError
except AttributeError:
    try:
        from stripe.error import SignatureVerificationError  # type: ignore
    except ImportError:
        SignatureVerificationError = getattr(stripe, "SignatureVerificationError", None)



def _event(body="{}", headers=None):
    return {"body": body, "headers": headers or {"Stripe-Signature": "sig"}}


def test_invalid_signature_returns_400(monkeypatch, lambda_ctx):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    with patch.object(
        stripe.Webhook,
        "construct_event",
        side_effect=SignatureVerificationError("bad", "sig")
    ):
        from services.billing import stripe_webhook_lambda
        event = {"headers": {"Stripe-Signature": "sig"}, "body": "{}"}
        resp = stripe_webhook_lambda.handler(event, lambda_ctx)
        assert resp["statusCode"] == 400


def test_malformed_event_returns_400(monkeypatch, lambda_ctx):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    # resp = mod.handler({"headers": {}}, None)  # no body
    resp = mod.handler({"headers": {}}, lambda_ctx)
    assert resp["statusCode"] == 400


def test_expired_signature(monkeypatch, lambda_ctx):
    """Simulate an expired timestamp in the signature header."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")

    event = {"headers": {"stripe-signature": "t=123,v1=fake"}, "body": "{}"}

    with patch("services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = SignatureVerificationError("Expired timestamp", "sig", "body")
        resp = mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 400
    assert "Invalid signature" in resp["body"]


def test_tampered_body(monkeypatch, lambda_ctx):
    """Simulate a payload that fails signature check (tampered body)."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")

    event = {"headers": {"stripe-signature": "sig"}, "body": '{"fake":"data"}'}

    with patch("services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event") as mock_construct:
        mock_construct.side_effect = SignatureVerificationError("Body was tampered", "sig", "body")
        resp = mod.handler(event, lambda_ctx)

    assert resp["statusCode"] == 400
    assert "Invalid signature" in resp["body"]


def test_missing_webhook_secret(monkeypatch, lambda_ctx):
    """If STRIPE_WEBHOOK_SECRET is missing, handler should raise RuntimeError."""
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}

    with pytest.raises(RuntimeError):
        mod.handler(event, lambda_ctx)



def test_missing_api_key_raises_runtimeerror(monkeypatch, lambda_ctx):
    """If STRIPE_SECRET_KEY is missing, handler should raise RuntimeError early."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    # Keep webhook secret set so we isolate the missing API key case
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake")

    event = {"headers": {"stripe-signature": "sig"}, "body": "{}"}
    with pytest.raises(RuntimeError):
        mod.handler(event, lambda_ctx)

