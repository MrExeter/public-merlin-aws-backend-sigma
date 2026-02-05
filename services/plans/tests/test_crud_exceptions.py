import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from decimal import Decimal
from services.plans import crud
from services.plans.models import Plan


@pytest.fixture
def sample_plan():
    """Fixture for a valid Plan instance matching actual model."""
    return Plan(
        name="Pro",
        description="Pro tier plan",
        price_usd=Decimal("9.99"),
        max_tokens=100000,
        active=True
    )


@patch("boto3.resource")
def test_create_plan_success(mock_boto, sample_plan, monkeypatch):
    """Validate successful DynamoDB write."""
    monkeypatch.setenv("PLANS_TABLE", "TestPlans")
    mock_table = MagicMock()
    mock_boto.return_value.Table.return_value = mock_table
    mock_table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    result = crud.create_plan(sample_plan)
    assert result is not None
    mock_table.put_item.assert_called_once()


@patch("boto3.resource")
def test_create_plan_client_error(mock_boto, sample_plan, monkeypatch):
    """Simulate a DynamoDB ClientError during write."""
    monkeypatch.setenv("PLANS_TABLE", "TestPlans")
    mock_table = MagicMock()
    mock_boto.return_value.Table.return_value = mock_table
    mock_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Duplicate"}},
        "PutItem"
    )

    with pytest.raises(ClientError):
        crud.create_plan(sample_plan)


def test_create_plan_missing_env(monkeypatch, sample_plan):
    """Ensure missing env variable or table triggers failure cleanly."""
    monkeypatch.delenv("PLANS_TABLE", raising=False)

    with patch("boto3.resource") as mock_boto:
        mock_boto.return_value.Table.side_effect = ValueError("Missing table name")

        with pytest.raises(ValueError):
            crud.create_plan(sample_plan)
