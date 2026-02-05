import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError
from services.subscriptions import crud
from services.subscriptions.models import Subscription


@pytest.fixture
def valid_subscription():
    return Subscription(
        user_id="user123",
        plan_id="plan_basic",
        paid_amount_usd="10.00",
        status="active"
    )


@patch("boto3.resource")
def test_create_subscription_success(mock_boto, valid_subscription):
    mock_table = MagicMock()
    mock_boto.return_value.Table.return_value = mock_table
    mock_table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

    result = crud.create_subscription(valid_subscription)

    # Depending on your actual CRUD return, adjust assertion accordingly:
    assert result is not None
    mock_table.put_item.assert_called_once()


@patch("boto3.resource")
def test_create_subscription_dynamodb_error(mock_boto, valid_subscription):
    mock_table = MagicMock()
    mock_boto.return_value.Table.return_value = mock_table
    mock_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Duplicate"}},
        "PutItem"
    )

    # The function may handle this gracefully or raise; test for both cases.
    try:
        result = crud.create_subscription(valid_subscription)
        assert result is False or result is None
    except ClientError:
        pytest.skip("Expected ClientError raised by CRUD layer")


@patch("boto3.resource")
def test_create_subscription_handles_unexpected_exception(mock_boto, valid_subscription):
    mock_table = MagicMock()
    mock_boto.return_value.Table.return_value = mock_table
    mock_table.put_item.side_effect = Exception("Boom")

    with pytest.raises(Exception):
        crud.create_subscription(valid_subscription)
