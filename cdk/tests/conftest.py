import pytest
import os

class FakeFormatterClient:
    """Simulates the FormatterLambda behavior."""

    VALID_CHANNELS = {"quota", "billing", "security", "tenant"}

    def __init__(self, slack):
        self.slack = slack

    def format_and_send(self, channel, payload):
        # ✅ If secret missing (explicitly ""), fail.
        secret = os.getenv("SLACK_WEBHOOK_SECRET")
        if secret == "":
            return False

        # If secret unset (None), fall back to default.
        if secret is None:
            secret = "dummy-secret"

        if not payload or "msg" not in payload:
            return False

        if channel not in self.VALID_CHANNELS:
            return False

        try:
            message = payload["msg"]
            if len(message) > 4000:
                message = message[:4000]
            self.slack.send_message(channel, message)
            return True
        except Exception:
            return False


@pytest.fixture
def formatter_client(slack_mock):
    """Fixture that provides a fake FormatterLambda client."""
    return FakeFormatterClient(slack_mock)
