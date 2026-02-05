# services/common/ddb_utils.py
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from services.common.time_utils import to_iso_z

def ddb_safe(value: Any):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, Decimal) or isinstance(value, int) or value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, datetime):
        return to_iso_z(value)
    if isinstance(value, Mapping):
        return {k: ddb_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        t = [ddb_safe(v) for v in value]
        return t if not isinstance(value, set) else set(t)
    return str(value)
