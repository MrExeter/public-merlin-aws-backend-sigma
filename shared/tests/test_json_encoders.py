import json
import datetime
from decimal import Decimal
from shared.utils.json_encoders import DecimalEncoder, json_dumps_safe


def test_decimal_encoder_converts_to_float():
    data = {"amount": Decimal("1.23")}
    encoded = json.dumps(data, cls=DecimalEncoder)
    assert '"amount": 1.23' in encoded


def test_json_dumps_safe_handles_decimal():
    data = {"price": Decimal("9.99")}
    result = json_dumps_safe(data)
    assert '"price": 9.99' in result


def test_json_dumps_safe_raises_for_invalid_type():
    class NonSerializable:
        pass

    data = {"bad": NonSerializable()}
    try:
        json_dumps_safe(data)
    except TypeError as e:
        assert "NonSerializable" in str(e)
    else:
        raise AssertionError("Expected TypeError not raised")
