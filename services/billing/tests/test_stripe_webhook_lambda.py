
def test_duplicate_event_id(monkeypatch, webhook_event_factory, lambda_context, fake_events_table):
    from services.billing import stripe_webhook_lambda
    import json

    event = webhook_event_factory(valid_signature=True, event_type="invoice.paid")

    # Mock out Stripe signature verification
    monkeypatch.setattr(
        "services.billing.stripe_webhook_lambda.stripe.Webhook.construct_event",
        staticmethod(lambda payload, sig, secret: json.loads(payload))
    )

    first = stripe_webhook_lambda.handler(event, lambda_context)
    assert first["statusCode"] in [200, 201]

    duplicate = stripe_webhook_lambda.handler(event, lambda_context)
    assert duplicate["statusCode"] == 200
