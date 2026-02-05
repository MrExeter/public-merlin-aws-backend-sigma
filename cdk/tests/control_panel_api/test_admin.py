# cdk/tests/control_panel_api/test_admin.py

import json
from types import SimpleNamespace

import pytest

from control_panel_api import admin_me, list_users, create_user, assign_roles
from .utils.fake_cognito import FakeCognitoClient, FakeBoto3


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


@pytest.fixture
def lambda_context():
    return SimpleNamespace(function_name="test_fn")


@pytest.fixture
def user_pool_id():
    return "us-west-1_fakepool"


# ---------------------------------------------------------------------
# GET /admin/me
# ---------------------------------------------------------------------


def test_admin_me_ok(lambda_context):
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "cognito:username": "alice",
                    "email": "alice@example.com",
                    "cognito:groups": ["Admins", "Developers"],
                    "custom:tenant_id": "tenant3012",
                }
            }
        }
    }

    resp = admin_me.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["groups"] == ["Admins", "Developers"]
    assert body["claims"]["custom:tenant_id"] == "tenant3012"


def test_admin_me_missing_claims(lambda_context):
    # No requestContext / authorizer / claims
    event = {}

    resp = admin_me.handler(event, lambda_context)
    assert resp["statusCode"] == 400

    body = json.loads(resp["body"])
    assert "missing auth claims" in body["error"].lower()


# ---------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------


def test_admin_list_users_ok(monkeypatch, lambda_context, user_pool_id):
    users = {
        "alice": {
            "Username": "alice",
            "Attributes": [{"Name": "email", "Value": "alice@example.com"}],
        },
        "bob": {
            "Username": "bob",
            "Attributes": [{"Name": "email", "Value": "bob@example.com"}],
        },
    }

    user_groups = {
        "alice": ["Admins"],
        "bob": ["ReadOnly"],
    }

    fake_client = FakeCognitoClient(users=users, user_groups=user_groups)
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(list_users, "boto3", fake_boto3)

    event = {
        "httpMethod": "GET",
        "path": "/admin/users",
    }

    resp = list_users.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 2
    assert len(body["users"]) == 2

    usernames = {u["username"] for u in body["users"]}
    assert {"alice", "bob"} == usernames

    # Check groups assigned
    alice = next(u for u in body["users"] if u["username"] == "alice")
    assert "Admins" in alice["groups"]


def test_admin_list_users_empty(monkeypatch, lambda_context, user_pool_id):
    fake_client = FakeCognitoClient(users={}, user_groups={})
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(list_users, "boto3", fake_boto3)

    event = {"httpMethod": "GET", "path": "/admin/users"}

    resp = list_users.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["count"] == 0
    assert body["users"] == []


# ---------------------------------------------------------------------
# POST /admin/users
# ---------------------------------------------------------------------


def test_admin_create_user_ok(monkeypatch, lambda_context, user_pool_id):
    from control_panel_api import create_user

    fake_client = FakeCognitoClient(users={}, user_groups={})
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(create_user, "boto3", fake_boto3)

    payload = {
        "username": "charlie",
        "email": "charlie@example.com",
        "groups": ["Admins", "Developers"],
    }

    event = {
        "httpMethod": "POST",
        "path": "/admin/users",
        "body": json.dumps(payload),
    }

    resp = create_user.handler(event, lambda_context)
    assert resp["statusCode"] == 201

    body = json.loads(resp["body"])
    assert body["username"] == "charlie"
    assert body["email"] == "charlie@example.com"
    assert set(body["groups"]) == {"Admins", "Developers"}

    # Ensure FakeCognito has the user & groups
    assert "charlie" in fake_client.users
    assert "Admins" in fake_client.user_groups["charlie"]
    assert "Developers" in fake_client.user_groups["charlie"]


def test_admin_create_user_invalid_body(monkeypatch, lambda_context, user_pool_id):
    from control_panel_api import create_user

    fake_client = FakeCognitoClient(users={}, user_groups={})
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(create_user, "boto3", fake_boto3)

    event = {
        "httpMethod": "POST",
        "path": "/admin/users",
        "body": "not-json",
    }

    resp = create_user.handler(event, lambda_context)
    assert resp["statusCode"] == 400

    body = json.loads(resp["body"])
    assert "invalid json" in body["error"].lower()


# ---------------------------------------------------------------------
# POST /admin/users/{username}/roles
# ---------------------------------------------------------------------


def test_assign_roles_ok(monkeypatch, lambda_context, user_pool_id):
    from control_panel_api import assign_roles

    # Start with existing user, no groups
    users = {
        "dana": {
            "Username": "dana",
            "Attributes": [{"Name": "email", "Value": "dana@example.com"}],
        }
    }

    user_groups = {"dana": []}

    fake_client = FakeCognitoClient(users=users, user_groups=user_groups)
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(assign_roles, "boto3", fake_boto3)

    payload = {"groups": ["Support", "ReadOnly"]}

    event = {
        "httpMethod": "POST",
        "path": "/admin/users/dana/roles",
        "pathParameters": {"username": "dana"},
        "body": json.dumps(payload),
    }

    resp = assign_roles.handler(event, lambda_context)
    assert resp["statusCode"] == 200

    body = json.loads(resp["body"])
    assert body["username"] == "dana"
    assert set(body["groups"]) == {"Support", "ReadOnly"}

    assert set(fake_client.user_groups["dana"]) == {"Support", "ReadOnly"}


def test_assign_roles_user_not_found(monkeypatch, lambda_context, user_pool_id):
    from control_panel_api import assign_roles

    fake_client = FakeCognitoClient(users={}, user_groups={})
    fake_boto3 = FakeBoto3(fake_client)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", user_pool_id)
    monkeypatch.setattr(assign_roles, "boto3", fake_boto3)

    payload = {"groups": ["Admins"]}

    event = {
        "httpMethod": "POST",
        "path": "/admin/users/ghost/roles",
        "pathParameters": {"username": "ghost"},
        "body": json.dumps(payload),
    }

    resp = assign_roles.handler(event, lambda_context)
    assert resp["statusCode"] == 404

    body = json.loads(resp["body"])
    assert "user not found" in body["error"].lower()
