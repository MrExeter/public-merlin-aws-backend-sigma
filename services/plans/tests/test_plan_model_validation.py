import pytest
from decimal import Decimal
from pydantic import ValidationError
from services.plans.models import Plan


def test_valid_plan_creation():
    """Ensure valid Plan initializes properly and assigns defaults."""
    plan = Plan(
        name="Starter",
        description="Basic tier",
        price_usd=Decimal("4.99"),
        max_tokens=10000,
        active=True
    )
    assert plan.plan_id
    assert isinstance(plan.price_usd, Decimal)
    assert plan.active is True
    assert plan.name == "Starter"


def test_invalid_decimal_value():
    """Invalid price_usd should raise a ValidationError."""
    with pytest.raises(ValidationError):
        Plan(
            name="Invalid",
            description="Bad price",
            price_usd="five dollars",  # invalid type
            max_tokens=1000,
            active=True
        )


def test_negative_max_tokens():
    with pytest.raises(ValidationError) as exc:
        Plan(
            name="Negative",
            description="Should fail",
            price_usd=Decimal("1.99"),
            max_tokens=-500,
            active=True
        )
    assert "max_tokens must be greater than 0" in str(exc.value)



def test_json_serialization_roundtrip():
    """Ensure model can dump and rehydrate properly with Decimal intact."""
    plan = Plan(
        name="Standard",
        description="Mid tier",
        price_usd=Decimal("9.99"),
        max_tokens=250000,
        active=True
    )
    data = plan.model_dump()
    restored = Plan(**data)
    assert restored.price_usd == Decimal("9.99")
    assert restored.max_tokens == 250000
    assert restored.name == "Standard"
