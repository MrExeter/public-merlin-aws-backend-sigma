import json
import pytest
from unittest.mock import patch, MagicMock
from services.subscriptions.lambdas import subscribe_user

@pytest.fixture
def sample_event():
    return {
        "body": json.dumps({
            "user_id": "user123",
            "plan_id": "plan_basic",
            "paid_amount_usd": "10.00"
        })
    }


@patch("services.subscriptions.lambdas.subscribe_user.create_subscription")
def test_subscribe_user_success(mock_create):
    mock_create.return_value = {"subscription_id": "abc123"}
    event = {
        "body": json.dumps({
            "user_id": "user123",
            "plan_id": "plan_basic",
            "paid_amount_usd": "10.00"
        })
    }
    response = subscribe_user.handler(event, None)
    assert response["statusCode"] in (200, 201)
    assert "subscription_id" in response["body"]

def test_invalid_json_body():
    bad_event = {"body": "{bad_json}"}
    response = subscribe_user.handler(bad_event, None)
    assert response["statusCode"] == 400
    # Allow either your raw JSON error or generic message
    assert "Expecting property name" in response["body"] or "Invalid JSON" in response["body"]


def test_missing_required_field(monkeypatch, sample_event):
    body = json.loads(sample_event["body"])
    del body["plan_id"]
    sample_event["body"] = json.dumps(body)
    response = subscribe_user.handler(sample_event, None)
    assert response["statusCode"] == 400
    assert "plan_id" in response["body"]

def test_invalid_decimal(monkeypatch, sample_event):
    body = json.loads(sample_event["body"])
    body["paid_amount_usd"] = "ten"
    sample_event["body"] = json.dumps(body)
    response = subscribe_user.handler(sample_event, None)
    assert response["statusCode"] == 400
    assert "paid_amount_usd" in response["body"]


@patch("services.subscriptions.lambdas.subscribe_user.create_subscription")
def test_dynamodb_failure(mock_create):
    mock_create.side_effect = Exception("DynamoDB failed")
    event = {"body": json.dumps({"user_id": "u1", "plan_id": "p1"})}
    response = subscribe_user.handler(event, None)
    assert response["statusCode"] in (400, 500)
    assert "error" in response["body"]
