import pytest
import json
from unittest.mock import patch, MagicMock
from services.plans.lambdas import create_plan


@patch("services.plans.lambdas.create_plan.create_plan")
def test_invalid_json_body(mock_create):
    event = {"body": "{invalid: json}"}
    response = create_plan.handler(event, None)
    assert response["statusCode"] == 400
    assert "Expecting property name" in response["body"] or "Invalid JSON" in response["body"]


@patch("services.plans.lambdas.create_plan.create_plan")
def test_missing_required_field(mock_create):
    body = {"plan_name": "Pro"}  # missing price_usd, max_tokens, etc.
    event = {"body": json.dumps(body)}
    response = create_plan.handler(event, None)
    assert response["statusCode"] == 400
    assert "price_usd" in response["body"] or "missing" in response["body"].lower()


@patch("services.plans.lambdas.create_plan.create_plan")
def test_dynamodb_failure(mock_create):
    mock_create.side_effect = Exception("DynamoDB insert failed")
    event = {
        "body": json.dumps({
            "plan_name": "Pro",
            "description": "Professional tier",
            "price_usd": "19.99",
            "max_tokens": 500000,
            "status": "active"
        })
    }
    response = create_plan.handler(event, None)
    assert response["statusCode"] in (400, 500)
    assert "error" in response["body"]
