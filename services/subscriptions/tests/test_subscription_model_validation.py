import pytest
from decimal import Decimal, InvalidOperation
from pydantic import ValidationError
from services.subscriptions.models import Subscription

def test_valid_subscription_creates_defaults():
    sub = Subscription(user_id="user123", plan_id="plan_basic", paid_amount_usd=Decimal("5.00"))
    # Validate required fields exist and are correctly typed
    assert sub.user_id == "user123"
    assert sub.plan_id == "plan_basic"
    assert isinstance(sub.paid_amount_usd, Decimal)

    # Optional defaults (only check if they exist)
    if hasattr(sub, "subscription_id"):
        assert sub.subscription_id  # not empty if defined
    if hasattr(sub, "status"):
        assert sub.status in {"active", "cancelled", "past_due"}

def test_missing_required_fields():
    with pytest.raises(ValidationError):
        Subscription(plan_id="plan_basic")  # Missing user_id

def test_invalid_status_value():
    with pytest.raises(ValidationError):
        Subscription(user_id="user123", plan_id="plan_basic", paid_amount_usd=Decimal("5.00"), status="expired")

def test_invalid_decimal_amount():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Subscription(user_id="user123", plan_id="plan_basic", paid_amount_usd="five dollars")

def test_json_serialization_round_trip():
    sub = Subscription(user_id="u1", plan_id="p1", paid_amount_usd=Decimal("10.25"))
    data = sub.model_dump()
    sub2 = Subscription(**data)
    assert sub2.paid_amount_usd == Decimal("10.25")
