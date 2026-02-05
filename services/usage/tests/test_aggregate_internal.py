import pytest
from datetime import datetime, timezone
import importlib
from services.usage import aggregation
from decimal import Decimal
from unittest.mock import MagicMock, patch
from services.usage.models import UsageSummary
import services.usage.lambdas.aggregate.handler as handler
from services.usage.lambdas.aggregate.handler import _ddb

# --- _ddb() / _tables() tests -------------------------------------------------

def test_tables_missing_env(monkeypatch):
    """Force reload handler to reset globals before testing env-var branch."""
    importlib.reload(handler)
    monkeypatch.delenv("USAGE_TABLE_NAME", raising=False)
    monkeypatch.delenv("TENANTS_TABLE_NAME", raising=False)

    with pytest.raises(RuntimeError):
        handler._tables.__wrapped__() if hasattr(handler._tables, "__wrapped__") else handler._tables()


def test_tables_initializes_once(monkeypatch):
    """Ensure _tables() initializes globals once after fresh reload."""
    importlib.reload(handler)

    fake_ddb = MagicMock()
    fake_ddb.Table.return_value = "mock_table"
    monkeypatch.setattr(handler, "_ddb", lambda: fake_ddb)
    monkeypatch.setenv("USAGE_TABLE_NAME", "UsageTable")
    monkeypatch.setenv("TENANTS_TABLE_NAME", "TenantsTable")

    t1, t2 = handler._tables()
    t3, t4 = handler._tables()
    assert t1 == t3 == "mock_table"
    assert t2 == t4 == "mock_table"

# --- _resolve_tenant() edge-case tests ----------------------------------------

def test_resolve_tenant_no_client():
    """If no client_id claim exists, should return 'unknown'."""
    event = {"requestContext": {"authorizer": {"claims": {}}}}
    tenant = handler._resolve_tenant(event, tenants_tbl=None)
    assert tenant == "unknown"


def test_resolve_tenant_ddb_exception(monkeypatch):
    """If Dynamo get_item raises, should fall back to 'unknown'."""
    fake_table = MagicMock()
    fake_table.get_item.side_effect = Exception("boom!")
    event = {"requestContext": {"authorizer": {"claims": {"client_id": "abc"}}}}
    tenant = handler._resolve_tenant(event, fake_table)
    assert tenant == "unknown"


def test_resolve_tenant_item_missing(monkeypatch):
    """If Dynamo returns no Item, should return 'unknown'."""
    fake_table = MagicMock()
    fake_table.get_item.return_value = {}
    event = {"requestContext": {"authorizer": {"claims": {"client_id": "xyz"}}}}
    tenant = handler._resolve_tenant(event, fake_table)
    assert tenant == "unknown"


# --- _parse_iso() tests -------------------------------------------------------

def test_parse_iso_valid_string():
    """Should parse a valid ISO8601 string."""
    ts = "2024-09-25T12:00:00Z"
    dt = handler._parse_iso(ts, None)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == timezone.utc


def test_parse_iso_invalid_returns_fallback():
    """Invalid ISO string should return the fallback value."""
    fallback = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dt = handler._parse_iso("invalid-date", fallback)
    assert dt == fallback


# --- defensive _ddb() test ----------------------------------------------------

def test_ddb_returns_boto_resource(monkeypatch):
    """Smoke test: _ddb returns a DynamoDB resource."""
    resource = _ddb()
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    assert "dynamodb" in str(type(resource)).lower() or "magicmock" in str(type(resource)).lower()


@patch("boto3.resource")
def test_aggregate_usage_creates_own_dynamodb(mock_boto3_resource):
    """Covers branch where dynamodb=None and boto3.resource() is used internally."""
    mock_ddb = MagicMock()
    mock_table = MagicMock()
    mock_ddb.Table.return_value = mock_table
    mock_table.query.return_value = {
        "Items": [
            {"tokens_used": 10, "cost_usd": "0.05"},
            {"tokens_used": 20, "cost_usd": "0.15"},
        ]
    }
    mock_boto3_resource.return_value = mock_ddb

    result = aggregation.aggregate_usage_for_user("u123", "2025-10-04")

    mock_boto3_resource.assert_called_once_with("dynamodb")
    mock_ddb.Table.assert_called_with(aggregation.get_usage_table_name())
    mock_table.query.assert_called_once()

    assert isinstance(result, UsageSummary)
    assert result.user_id == "u123"
    assert result.tokens_used == 30
    assert result.requests == 2
    assert result.cost_usd == Decimal("0.20")
