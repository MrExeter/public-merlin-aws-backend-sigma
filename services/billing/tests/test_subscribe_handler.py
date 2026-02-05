import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# 🧪 Add Lambda Layer to sys.path (for stripe import)
LAYER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lambdas", "python"))
sys.path.insert(0, LAYER_PATH)

# ✅ Load .env.local for tests
from dotenv import load_dotenv
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(dotenv_path=dotenv_path)

# ✅ Now import the handler module
from services.billing.lambdas import subscribe_lambda as handler_mod


@pytest.fixture
def valid_event():
    return {
        "body": json.dumps({
            "email": "user@example.com",
            "tenant_id": "tenant-123"
        })
    }


@patch.dict(os.environ, {
    "STRIPE_SECRET_KEY": "sk_test_dummy",
    "STRIPE_PRICE_ID": "price_dummy",
    "SUBSCRIPTIONS_TABLE": "dummy_table"
})
def test_valid_subscription_returns_200(valid_event):
    with patch("services.billing.lambdas.subscribe_lambda.stripe.Customer.create") as mock_create_customer, \
         patch("services.billing.lambdas.subscribe_lambda.stripe.Subscription.create") as mock_create_subscription, \
         patch("services.billing.lambdas.subscribe_lambda.subscriptions_table.put_item") as mock_put_item:

        mock_create_customer.return_value = MagicMock(id="cus_test123")
        mock_create_subscription.return_value = MagicMock(id="sub_test456", status="active")

        response = handler_mod.handler(valid_event, None)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert body["customer_id"] == "cus_test123"
        assert body["subscription_id"] == "sub_test456"
        assert body["status"] == "active"



def test_missing_email_returns_400():
    event = {
        "body": json.dumps({
            "tenant_id": "tenant-123"
        })
    }
    response = handler_mod.handler(event, None)
    assert response["statusCode"] == 400
    assert "error" in json.loads(response["body"])


def test_stripe_error_returns_500(valid_event):
    with patch("services.billing.lambdas.subscribe_lambda.stripe.Customer.create", side_effect=Exception("Stripe error")):
        response = handler_mod.handler(valid_event, None)
        assert response["statusCode"] == 500
        assert "error" in json.loads(response["body"])
