import pytest
import uuid
import time


# --- Fake Auth Client (mocking Cognito) ---
class FakeAuthClient:
    def __init__(self, slack=None):
        self.users = {}
        self.tokens = {}
        self.slack = slack
        self.failed_logins = {}

    def signup(self, payload):
        if "username" not in payload or "password" not in payload or "email" not in payload:
            return False
        if payload["username"] in self.users:
            return False
        self.users[payload["username"]] = payload
        return True

    def login(self, username, password):
        user = self.users.get(username)
        if not user or user["password"] != password:
            # track failed attempts
            self.failed_logins[username] = self.failed_logins.get(username, 0) + 1
            if self.failed_logins[username] >= 5 and self.slack:
                self.slack.send_message("security", f"Multiple failed login attempts for {username}")
            return False

        # success: issue token
        token = str(uuid.uuid4())
        self.tokens[token] = {"username": username, "exp": time.time() + 60}
        return token  # ✅ return token string, not bool

    def validate_token(self, token):
        data = self.tokens.get(token)
        if not data:
            return False
        if data["exp"] < time.time():
            return False
        return True

    def logout(self, token):
        if token in self.tokens:
            del self.tokens[token]

    def perform_admin_action(self, user):
        return user.get("role") == "admin"

    def access_resource(self, user, resource_tenant):
        return user.get("tenant_id") == resource_tenant

    def authenticate(self, user):
        return True  # no-op for now

    def get_config(self):
        return {"region": "us-west-1"}


# --- Fixtures ---

@pytest.fixture
def auth_client(slack_mock):
    return FakeAuthClient(slack=slack_mock)


@pytest.fixture
def token_factory(auth_client):
    """Generate valid or expired tokens via the fake auth_client."""
    def _make_token(expired=False):
        token = str(uuid.uuid4())
        exp = time.time() - 60 if expired else time.time() + 60
        auth_client.tokens[token] = {"username": "testuser", "exp": exp}
        return token
    return _make_token


@pytest.fixture
def iam_role_checker():
    def _check(role_name):
        return [
            {"Action": "cognito:InitiateAuth", "Resource": "arn:aws:cognito-idp:us-west-1:123456789012:userpool/mock"}
        ]
    return _check
