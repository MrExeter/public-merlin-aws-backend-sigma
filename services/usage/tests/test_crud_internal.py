import os
import pytest
from unittest.mock import patch, MagicMock
from services.usage import crud
from services.usage.models import UsageRecord


def test_get_usage_table_name_default(monkeypatch):
    """When no env var is set, should return the default constant."""
    monkeypatch.delenv("USAGE_TABLE_NAME", raising=False)
    assert crud.get_usage_table_name() == crud.DEFAULT_USAGE_TABLE_NAME


@patch("boto3.resource")
def test_log_usage_creates_own_dynamodb(mock_boto3_resource):
    """Covers the branch where dynamodb=None and boto3.resource() is invoked."""
    mock_ddb = MagicMock()
    mock_table = MagicMock()
    mock_ddb.Table.return_value = mock_table
    mock_boto3_resource.return_value = mock_ddb

    record = UsageRecord(
        user_id="user_auto",
        plan_id="plan_auto",
        endpoint="/ai/test",
        tokens_used=50,
        duration_ms=5,
        success=True,
    )

    result = crud.log_usage(record)  # no dynamodb passed

    # Ensure boto3.resource() was called internally
    mock_boto3_resource.assert_called_once_with("dynamodb")
    mock_ddb.Table.assert_called_with(crud.get_usage_table_name())

    # Ensure record persisted through ddb_safe pipeline
    mock_table.put_item.assert_called_once()
    assert result["user_id"] == "user_auto"
    assert "plan_id" in result
