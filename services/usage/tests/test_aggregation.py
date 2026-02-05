# services/usage/tests/test_aggregation.py
from decimal import Decimal
from moto import mock_aws
import boto3

from services.common.time_utils import now_utc
from services.usage.models import UsageRecord
from services.usage.aggregation import aggregate_usage_for_user
from services.usage.crud import get_usage_table_name
from services.usage import aggregation
from services.usage.lambdas.aggregate import handler as aggy_handler



def test_aggregate_usage_for_user():
    """Verifies token and cost aggregation with an injected fake DynamoDB."""
    class FakeTable:
        def query(self, **kwargs):
            return {"Items": [{
                "user_id": "user123",
                "timestamp": "2025-09-25T12:00:00Z",
                "tokens_used": 500,
                "cost_usd": "1.23",
            }]}

    class FakeDdb:
        def Table(self, name):
            return FakeTable()

    result = aggregation.aggregate_usage_for_user("user123", "2025-09-25", dynamodb=FakeDdb())

    assert result.user_id == "user123"
    assert result.tokens_used == 500
    assert result.requests == 1
    assert float(result.cost_usd) == 1.23



def test_aggregate_usage_for_user_no_items(monkeypatch):
    # Patch dynamodb.Table.query to return empty
    class FakeTable:
        def query(self, **kwargs):
            return {"Items": []}

    class FakeDdb:
        def Table(self, name): return FakeTable()

    result = aggregation.aggregate_usage_for_user("user123", "2025-09-25", dynamodb=FakeDdb())
    assert result.user_id == "user123"
    assert result.tokens_used == 0
    assert result.requests == 0
    assert float(result.cost_usd) == 0.0
