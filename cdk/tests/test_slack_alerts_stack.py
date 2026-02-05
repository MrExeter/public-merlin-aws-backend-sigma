import pytest


# --- Sad-path tests ---

def test_slack_webhook_unavailable(formatter_client, slack_mock, monkeypatch):
    """FormatterLambda should handle Slack webhook failures gracefully."""

    def fail_send(channel, text):
        raise ConnectionError("Slack API unreachable")

    monkeypatch.setattr(slack_mock, "send_message", fail_send)

    result = formatter_client.format_and_send("quota", {"error": "QuotaExceeded"})
    assert result is False  # expect graceful failure, not crash


def test_invalid_channel_rejected(formatter_client, slack_mock):
    """Sending to invalid channel should fail without crashing."""
    result = formatter_client.format_and_send("nonexistent", {"msg": "test"})
    assert result is False
    assert slack_mock.get_messages("nonexistent") == []


def test_malformed_alert_payload(formatter_client, slack_mock):
    """Malformed payload should be rejected cleanly."""
    result = formatter_client.format_and_send("quota", {"bad_key": "oops"})
    assert result is False
    assert slack_mock.get_messages("quota") == []


# --- Edge-case tests ---

def test_empty_message_body(formatter_client, slack_mock):
    """Empty payload should not post to Slack."""
    result = formatter_client.format_and_send("quota", {})
    assert result is False
    assert slack_mock.get_messages("quota") == []


def test_large_message_truncated(formatter_client, slack_mock):
    """Very large messages should be truncated, not crash."""
    big_msg = {"msg": "X" * 5000}
    result = formatter_client.format_and_send("quota", big_msg)
    assert result is True

    msgs = slack_mock.get_messages("quota")
    assert len(msgs) == 1
    assert len(msgs[0]) <= 4000  # Slack limit safeguard


def test_unicode_characters_allowed(formatter_client, slack_mock):
    """Unicode/emojis should post without issues."""
    payload = {"msg": "🚀 All good!"}
    result = formatter_client.format_and_send("quota", payload)
    assert result is True
    assert "🚀" in slack_mock.get_messages("quota")[0]


# --- Integration tests ---

def test_routing_to_multiple_channels(formatter_client, slack_mock):
    """Different alert types should route to correct Slack channels."""
    formatter_client.format_and_send("quota", {"msg": "Quota alert"})
    formatter_client.format_and_send("billing", {"msg": "Billing alert"})
    formatter_client.format_and_send("security", {"msg": "Security alert"})

    assert any("Quota" in msg for msg in slack_mock.get_messages("quota"))
    assert any("Billing" in msg for msg in slack_mock.get_messages("billing"))
    assert any("Security" in msg for msg in slack_mock.get_messages("security"))


def test_tenant_alerts_are_sanitized(formatter_client, slack_mock):
    """Tenant-facing alerts should have sensitive info stripped."""
    payload = {"msg": "QuotaExceeded", "secret": "do-not-leak"}
    formatter_client.format_and_send("tenant", payload)

    msgs = slack_mock.get_messages("tenant")
    assert all("do-not-leak" not in msg for msg in msgs)


# --- Infra/Security tests ---

def test_slack_secret_missing(monkeypatch, formatter_client):
    """Should fail gracefully if Slack secret is missing."""
    monkeypatch.setenv("SLACK_WEBHOOK_SECRET", "")
    result = formatter_client.format_and_send("quota", {"msg": "test"})
    assert result is False
