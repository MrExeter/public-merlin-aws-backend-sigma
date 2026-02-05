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

@pytest.fixture
def slack_mock():
    return SlackMock()
