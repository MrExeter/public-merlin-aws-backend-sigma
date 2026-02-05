# services/usage/tests/test_crud.py
import pytest
from unittest.mock import MagicMock
from services.usage.crud import log_usage, UsageRecord, get_usage_table_name
from services.usage import crud

@pytest.fixture
def mock_ddb_resource():
    mock_table = MagicMock()
    mock_resource = MagicMock()
    mock_resource.Table.return_value = mock_table
    return mock_resource, mock_table

def test_log_usage_success(mock_ddb_resource):
    mock_resource, mock_table = mock_ddb_resource

    record = UsageRecord(
        user_id="user_123",
        plan_id="plan_pro",
        endpoint="/ai/infer",
        tokens_used=200,
        duration_ms=55,
        success=True,
    )

    r1 = log_usage(record, dynamodb=mock_resource)
    r2 = log_usage(record, dynamodb=mock_resource)

    # ✅ Assert against the same resolution logic the code uses
    mock_resource.Table.assert_called_with(get_usage_table_name())
    assert mock_table.put_item.call_count == 2
    assert r1["user_id"] == "user_123" and r1["tokens_used"] == 200
    assert r2["user_id"] == "user_123" and r2["tokens_used"] == 200


def test_log_usage_handles_custom_dynamodb(monkeypatch):
    class FakeTable:
        def put_item(self, Item): return {"ok": True}

    class FakeDdb:
        def Table(self, name): return FakeTable()

    record = crud.UsageRecord(
        user_id="u1", plan_id="p1", endpoint="/test", tokens_used=1, duration_ms=10, success=True
    )
    result = crud.log_usage(record, dynamodb=FakeDdb())
    assert result["user_id"] == "u1"
    assert result["plan_id"] == "p1"
