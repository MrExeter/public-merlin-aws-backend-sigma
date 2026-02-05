# conftest.py (repo root)
import pytest

class SlackMock:
    def __init__(self):
        self.messages = {}

    def send_message(self, channel, text):
        if channel not in self.messages:
            self.messages[channel] = []
        self.messages[channel].append(text)

    def get_messages(self, channel):
        return self.messages.get(channel, [])


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-1")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "dummy")
    monkeypatch.setenv("STRIPE_API_KEY", "dummy")
    monkeypatch.setenv("STRIPE_PRICE_ID", "dummy")
    monkeypatch.setenv("STRIPE_PRODUCT_ID", "dummy")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "dummy")
    monkeypatch.setenv("SUBSCRIPTIONS_TABLE", "dummy")

@pytest.fixture
def slack_mock():
    return SlackMock()
