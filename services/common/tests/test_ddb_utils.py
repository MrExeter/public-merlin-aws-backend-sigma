# services/common/tests/test_ddb_utils.py
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from services.common.ddb_utils import ddb_safe

def test_float_to_decimal():
    out = ddb_safe(3.14)
    assert isinstance(out, Decimal)
    assert str(out) == "3.14"

def test_decimal_passthrough():
    d = Decimal("9.99")
    assert ddb_safe(d) is d

def test_int_bool_str_none_passthrough():
    assert ddb_safe(42) == 42
    assert ddb_safe(True) is True
    assert ddb_safe("x") == "x"
    assert ddb_safe(None) is None

def test_datetime_to_iso_z():
    dt = datetime(2025, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
    iso = ddb_safe(dt)
    assert iso.endswith("Z")
    assert iso.startswith("2025-09-25T12:00:00")

def test_mapping_recursive():
    payload = {"a": 1, "b": 2.5, "c": {"d": 3.5}}
    out = ddb_safe(payload)
    assert out["a"] == 1
    assert isinstance(out["b"], Decimal) and str(out["b"]) == "2.5"
    assert isinstance(out["c"]["d"], Decimal) and str(out["c"]["d"]) == "3.5"

def test_list_tuple_set_recursive_and_set_preserved_as_set():
    out_list = ddb_safe([1, 2.5])
    assert out_list == [1, Decimal("2.5")]
    out_tuple = ddb_safe((1, 2.5))
    assert out_tuple == [1, Decimal("2.5")]  # tuples become lists per implementation
    out_set = ddb_safe({1, 2.5})
    assert isinstance(out_set, set)
    assert Decimal("2.5") in out_set

def test_fallback_to_str_for_unknown_types():
    obj = SimpleNamespace(foo="bar")
    out = ddb_safe(obj)
    # ddb_safe falls back to str(x), which for SimpleNamespace looks like this:
    assert out == "namespace(foo='bar')"
