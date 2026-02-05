# services/plans/tests/test_handler.py

import json
from unittest.mock import patch
from services.plans.models import Plan
from services.plans.lambdas.create_plan import handler


def test_create_plan_handler_success():
    payload = {
        "name": "Startup",
        "description": "Great for early teams",
        "price_usd": 14.99,
        "max_tokens": 25000
    }

    fake_plan = Plan(**payload)

    with patch("services.plans.lambdas.create_plan.create_plan") as mock_create:
        mock_create.return_value = fake_plan.model_dump()

        event = {"body": json.dumps(payload)}
        result = handler(event, None)
        body = json.loads(result["body"])

        print(f"Response: {result}")

        assert result["statusCode"] == 201
        assert body["name"] == "Startup"
        assert body["price_usd"] == 14.99

