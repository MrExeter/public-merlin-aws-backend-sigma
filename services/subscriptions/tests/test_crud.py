import pytest
import boto3
from moto import mock_aws
from decimal import Decimal
from services.subscriptions.models import Subscription
from services.subscriptions.crud import create_subscription

TABLE_NAME = "SubscriptionsTable"

@pytest.fixture
def dynamodb():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "subscription_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "subscription_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.resource("dynamodb", region_name="us-east-1")

def test_create_subscription_valid(dynamodb):
    sub = Subscription(subscription_id="sub1", user_id="u1", plan_id="basic", paid_amount_usd=Decimal("10.0"))
    created = create_subscription(sub, dynamodb)
    assert created["subscription_id"] == "sub1"
    assert created["status"] == "active"

def test_create_subscription_duplicate_overwrites(dynamodb):
    sub1 = Subscription(subscription_id="sub1", user_id="u1", plan_id="basic", paid_amount_usd=Decimal("10.0"))
    sub2 = Subscription(subscription_id="sub1", user_id="u1", plan_id="pro", paid_amount_usd=Decimal("20.0"))
    create_subscription(sub1, dynamodb)
    result = create_subscription(sub2, dynamodb)
    assert result["plan_id"] == "pro"  # overwrote plan
    table = dynamodb.Table(TABLE_NAME)
    item = table.get_item(Key={"subscription_id": "sub1"})["Item"]
    assert item["plan_id"] == "pro"

def test_create_subscription_invalid_amount(dynamodb):
    with pytest.raises(Exception):
        Subscription(subscription_id="sub2", user_id="u2", plan_id="basic", paid_amount_usd="invalid")


def test_duplicate_subscription_id_overwrites(dynamodb):
    sub1 = Subscription(subscription_id="sub-edge", user_id="u1", plan_id="basic", paid_amount_usd=Decimal("10.0"))
    sub2 = Subscription(subscription_id="sub-edge", user_id="u1", plan_id="pro", paid_amount_usd=Decimal("20.0"))
    create_subscription(sub1, dynamodb)
    result = create_subscription(sub2, dynamodb)
    assert result["plan_id"] == "pro"  # overwrite confirmed
    table = dynamodb.Table(TABLE_NAME)
    item = table.get_item(Key={"subscription_id": "sub-edge"})["Item"]
    assert item["plan_id"] == "pro"


def test_status_cancelled_persists(dynamodb):
    sub = Subscription(subscription_id="sub-cancel", user_id="u2", plan_id="basic", paid_amount_usd=Decimal("15.0"))
    sub.status = "cancelled"
    created = create_subscription(sub, dynamodb)
    assert created["status"] == "cancelled"


def test_status_past_due_persists(dynamodb):
    sub = Subscription(subscription_id="sub-pastdue", user_id="u3", plan_id="pro", paid_amount_usd=Decimal("30.0"))
    sub.status = "past_due"
    created = create_subscription(sub, dynamodb)
    assert created["status"] == "past_due"
