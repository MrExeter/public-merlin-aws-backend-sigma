from unittest.mock import MagicMock
from services.subscriptions import crud, models

def test_create_subscription_writes_to_table():
    fake_table = MagicMock()
    fake_dynamo = MagicMock()
    fake_dynamo.Table.return_value = fake_table

    sub = models.Subscription(user_id="u1", plan_id="basic", paid_amount_usd=9.99)
    item = crud.create_subscription(sub, dynamodb=fake_dynamo)

    fake_table.put_item.assert_called_once()
    assert item["user_id"] == "u1"
    assert item["plan_id"] == "basic"


def test_create_subscription_puts_item_in_table():
    fake_table = MagicMock()
    fake_dynamo = MagicMock()
    fake_dynamo.Table.return_value = fake_table

    sub = models.Subscription(user_id="u1", plan_id="basic", paid_amount_usd=9.99)
    item = crud.create_subscription(sub, dynamodb=fake_dynamo)

    # Ensure DynamoDB put_item was called
    fake_table.put_item.assert_called_once()
    # Returned item matches Subscription fields
    assert item["user_id"] == "u1"
    assert item["plan_id"] == "basic"
    assert "subscription_id" in item
