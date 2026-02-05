# services/usage/tests/conftest.py
import pytest
import os
import uuid
import time
import types

from unittest.mock import MagicMock
from types import SimpleNamespace
import boto3
from moto import mock_aws


@pytest.fixture
def lambda_ctx():
    ctx = types.SimpleNamespace()
    ctx.function_name = "test-func"
    ctx.aws_request_id = "req-123"
    ctx.memory_limit_in_mb = 128
    ctx.invoked_function_arn = "arn:aws:lambda:local:test"
    return ctx


@pytest.fixture
def usage_env(monkeypatch):
    monkeypatch.setenv("USAGE_TABLE_NAME", "mock_table")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "mock_tenants")
    monkeypatch.setenv("QUOTA_TABLE_NAME", "mock_quota")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ["USAGE_TABLE_NAME", "TENANTS_TABLE_NAME", "QUOTA_TABLE_NAME"]:
        monkeypatch.delenv(var, raising=False)

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageLogs-dev")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "Tenants-dev")
    monkeypatch.setenv("QUOTA_TABLE_NAME", "QuotaPlans-dev")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-1")


@pytest.fixture(autouse=True)
def mock_all_dynamodb(monkeypatch):
    """Mock all DynamoDB tables for tenant, quota, and usage lookups."""
    mock_ddb = MagicMock()
    mock_table = MagicMock()

    def fake_get_item(*_args, **_kwargs):
        key = _kwargs.get("Key") or {}
        if "tenant_id" in key:
            tenant_id = key["tenant_id"]
            return {
                "Item": {
                    "tenant_id": tenant_id,
                    "plan_id": "free-plan-dev",
                    "quota_limit": 10000,
                    "quota_used": 0,
                    "plan_type": "free",
                }
            }
        if "plan_id" in key:
            plan_id = key["plan_id"]
            return {
                "Item": {
                    "plan_id": plan_id,
                    "tenant_id": "t-1",
                    "plan_type": "free",
                    "quota_limit": 10000,
                    "quota_used": 0,
                }
            }
        # Default empty response
        print("🧪 fake_get_item returning:", _kwargs.get("Key"), "=>", {"Item": {...}})

        return {"Item": {"tenant_id": "t-1"}}

    def fake_put_item(*_args, **_kwargs):
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    mock_table.get_item.side_effect = fake_get_item
    mock_table.put_item.side_effect = fake_put_item
    mock_ddb.Table.return_value = mock_table

    # Replace all boto3.resource("dynamodb") calls with our mock
    monkeypatch.setattr(boto3, "resource", lambda *a, **kw: mock_ddb)
    yield



@pytest.fixture
def mock_dynamodb_tables():
    usage_table = MagicMock()
    tenants_table = MagicMock()
    quota_table = MagicMock()

    # Tenants Table: maps client_id to tenant_id
    tenants_table.get_item.return_value = {
        "Item": {
            "client_id": "abc123",
            "tenant_id": "tenant-1",
            "app_id": "my-app",
            "plan_id": "free-plan-dev"
        }
    }

    # Quota Table: plan_id -> quota_limit
    quota_table.get_item.return_value = {
        "Item": {
            "quota_limit": 1000
        }
    }

    # Usage Table: current token usage
    usage_table.query.return_value = {
        "Items": [{"token_count": 200}]
    }

    return usage_table, tenants_table, quota_table


class FakeUsageApiClient:
    """Simulates Usage API behavior with basic auth + quota tracking."""

    def __init__(self, quota_client, auth_client=None):
        self.quota_client = quota_client
        self.auth_client = auth_client
        self.logs = {}

    def log_usage(self, tenant_id, token, amount):
        # Require auth
        if not self._validate_token(token, tenant_id):
            return {"status": 401, "message": "Unauthorized"}

        # Check quota
        try:
            self.quota_client.consume(tenant_id, amount)
        except Exception as e:
            return {"status": 403, "message": str(e)}

        # Record usage
        self.logs.setdefault(tenant_id, 0)
        self.logs[tenant_id] += amount
        return {"status": 200, "message": "Usage logged"}

    def aggregate_usage(self, tenant_id, token):
        if not self._validate_token(token, tenant_id):
            return {"status": 401, "message": "Unauthorized"}
        return {"status": 200, "total": self.logs.get(tenant_id, 0)}

    def _validate_token(self, token, tenant_id):
        if not self.auth_client:
            return True  # bypass if no auth
        return self.auth_client.validate_token(token)


@pytest.fixture
def usage_api_client(quota_client, auth_client):
    """Provides a fake Usage API client with quota + auth integration."""
    return FakeUsageApiClient(quota_client, auth_client)


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
            self.failed_logins[username] = self.failed_logins.get(username, 0) + 1
            if self.failed_logins[username] >= 5 and self.slack:
                self.slack.send_message("security", f"Multiple failed login attempts for {username}")
            return False
        token = str(uuid.uuid4())
        self.tokens[token] = {"username": username, "exp": time.time() + 60}
        return token

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

    def get_config(self):
        return {"region": "us-west-1"}


@pytest.fixture(scope="function")
def auth_client(slack_mock):
    return FakeAuthClient(slack=slack_mock)


@pytest.fixture(scope="function")
def token_factory(auth_client):
    def _make_token(expired=False):
        token = str(uuid.uuid4())
        exp = time.time() - 60 if expired else time.time() + 60
        auth_client.tokens[token] = {"username": "testuser", "exp": exp}
        return token
    return _make_token


@pytest.fixture
def ddb_env(monkeypatch):
    """
    Creates isolated DynamoDB tables matching exactly what handler.py expects.
    """

    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageTable")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "TenantsTable")
    monkeypatch.setenv("QUOTA_TABLE_NAME", "QuotaTable")

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")

        # UsageTable
        ddb.create_table(
            TableName="UsageTable",
            KeySchema=[
                {"AttributeName": "tenant_month", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "tenant_month", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # TenantsTable
        ddb.create_table(
            TableName="TenantsTable",
            KeySchema=[{"AttributeName": "tenant_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "tenant_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # QuotaTable
        ddb.create_table(
            TableName="QuotaTable",
            KeySchema=[{"AttributeName": "plan_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "plan_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        yield ddb


@pytest.fixture(autouse=True)
def usage_dynamodb_mock(monkeypatch):
    """Usage-only DynamoDB mock — runs alongside global fixtures."""
    print("✅ usage_dynamodb_mock active (local)")
    mock_ddb = MagicMock()
    mock_table = MagicMock()

    def fake_get_item(*_args, **_kwargs):
        key = _kwargs.get("Key") or {}
        if "tenant_id" in key:
            return {
                "Item": {
                    "tenant_id": key["tenant_id"],
                    "plan_id": "free-plan-dev",
                    "quota_limit": 10000,
                    "quota_used": 0,
                }
            }
        if "plan_id" in key:
            return {
                "Item": {
                    "plan_id": key["plan_id"],
                    "tenant_id": "t-1",
                    "quota_limit": 10000,
                }
            }
        return {"Item": {"tenant_id": "t-1"}}

    def fake_put_item(*_args, **_kwargs):
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    mock_table.get_item.side_effect = fake_get_item
    mock_table.put_item.side_effect = fake_put_item
    mock_ddb.Table.return_value = mock_table
    monkeypatch.setattr(boto3, "resource", lambda *a, **kw: mock_ddb)
    yield

