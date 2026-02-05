import pytest


# --- Sad-path tests ---

def test_invalid_login_rejected(auth_client):
    """Wrong username or password should fail login."""
    result = auth_client.login("wronguser", "badpass")
    assert result is False


def test_expired_token_rejected(auth_client, token_factory):
    """Expired JWT should be rejected."""
    expired_token = token_factory(expired=True)
    result = auth_client.validate_token(expired_token)
    assert result is False


def test_unauthorized_role_denied(auth_client, auth_user_factory):
    """Non-admin should not be able to perform admin action."""
    user = auth_user_factory(role="user")
    result = auth_client.perform_admin_action(user)
    assert result is False


# --- Edge-case tests ---

def test_cross_tenant_access_blocked(auth_client, auth_user_factory):
    """Tenant A user should not access Tenant B's resource."""
    user_a = auth_user_factory(role="user", tenant_id="tenant-a")
    result = auth_client.access_resource(user=user_a, resource_tenant="tenant-b")
    assert result is False


def test_token_reuse_rejected(auth_client, token_factory):
    """Replay attack: reused token should be invalid after logout."""
    token = token_factory()
    auth_client.logout(token)
    result = auth_client.validate_token(token)
    assert result is False


def test_malformed_signup_rejected(auth_client):
    """Signup with missing fields should fail."""
    bad_payload = {"username": "alice"}  # missing password, email
    result = auth_client.signup(bad_payload)
    assert result is False


# --- Integration tests ---

def test_user_created_in_cognito_can_login(auth_client):
    payload = {"username": "bob", "password": "secure123", "email": "bob@example.com"}
    assert auth_client.signup(payload) is True

    token = auth_client.login("bob", "secure123")
    assert isinstance(token, str)
    assert len(token) > 0


def test_authenticated_request_consumes_quota(auth_client, quota_client, auth_user_factory):
    tenant_id = "tenant-123"
    user = auth_user_factory(role="user", tenant_id=tenant_id)
    quota_client.set_quota(tenant_id, 5)

    # Authenticate (stubbed)
    assert auth_client.authenticate(user) is True

    # Simulate request → consume quota
    quota_client.consume(tenant_id, 1)
    assert quota_client.remaining(tenant_id) == 4


def test_failed_logins_trigger_security_alert(auth_client, slack_mock):
    """Multiple failed login attempts should send Slack alert to #security."""
    for _ in range(5):
        auth_client.login("baduser", "badpass")

    msgs = slack_mock.get_messages("security")
    assert any("failed login" in msg.lower() for msg in msgs)


# --- Infra/Security tests ---

def test_auth_lambda_has_least_privilege(iam_role_checker):
    """Auth Lambda should not have wildcard IAM permissions."""
    role_policies = iam_role_checker("AuthLambdaRole")
    for stmt in role_policies:
        assert stmt["Action"] != "*"
        assert stmt["Resource"] != "*"


def test_no_hardcoded_secrets(auth_client):
    """Auth client should not expose hardcoded client IDs/secrets."""
    config = auth_client.get_config()
    assert "hardcoded-secret" not in config.values()
