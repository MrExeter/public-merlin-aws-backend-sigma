import boto3
import pytest
from moto import mock_aws
import os

from services.plans.crud import create_plan
from services.plans.models import Plan


@pytest.fixture
def dynamodb_table():
    """Spin up a fake DynamoDB table for plans."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-west-1")
        table_name = "PlansTable"
        client.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "plan_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "plan_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        os.environ["PLANS_TABLE_NAME"] = table_name
        yield boto3.resource("dynamodb", region_name="us-west-1").Table(table_name)


# --- Existing Happy Path ---
def test_create_plan_inserts_item(dynamodb_table):
    plan = Plan(
        plan_id="pro",
        name="Pro Plan",
        description="Pro plan with 1000 tasks",
        price_usd=99,
        max_tokens=1000,
        active=True,
    )
    create_plan(plan)

    resp = dynamodb_table.get_item(Key={"plan_id": "pro"})
    assert "Item" in resp
    assert resp["Item"]["plan_id"] == "pro"
    assert resp["Item"]["price_usd"] == 99
    assert resp["Item"]["max_tokens"] == 1000


# --- New Sad Path Tests ---

def test_create_plan_duplicate_plan_id(dynamodb_table):
    """Creating the same plan twice should overwrite (DynamoDB default)."""
    plan = Plan(
        plan_id="pro",
        name="Pro Plan",
        description="Pro plan with 1000 tasks",
        price_usd=99,
        max_tokens=1000,
        active=True,
    )
    create_plan(plan)
    create_plan(plan)  # second insert

    resp = dynamodb_table.get_item(Key={"plan_id": "pro"})
    assert "Item" in resp
    assert resp["Item"]["name"] == "Pro Plan"


def test_create_plan_missing_required_field(dynamodb_table):
    """Plan missing required fields should fail gracefully."""
    with pytest.raises(Exception):
        Plan(
            plan_id="invalid",
            name=None,  # required
            description="",
            price_usd=0,
            max_tokens=0,
            active=True,
        )


# --- Seeded Plans Test ---

@pytest.mark.parametrize(
    "plan_id, price_usd, max_tokens, overage",
    [
        ("freemium", 0, 50, 0.25),
        ("pro", 99, 1000, 0.15),
        ("business", 499, 5000, 0.10),
        ("enterprise", 2000, 25000, 0.05),
    ],
)
def test_seeded_plan_structure(dynamodb_table, plan_id, price_usd, max_tokens, overage):
    """Insert sample plan data from pricing model and confirm structure."""
    plan = Plan(
        plan_id=plan_id,
        name=f"{plan_id.title()} Plan",
        description=f"{plan_id.title()} tier test",
        price_usd=price_usd,
        max_tokens=max_tokens,
        active=True,
    )
    create_plan(plan)

    resp = dynamodb_table.get_item(Key={"plan_id": plan_id})
    assert "Item" in resp
    assert resp["Item"]["plan_id"] == plan_id
    assert resp["Item"]["price_usd"] == price_usd
    assert resp["Item"]["max_tokens"] == max_tokens
