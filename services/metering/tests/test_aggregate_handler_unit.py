# services/metering/tests/test_aggregate_handler_unit.py
import pytest
from unittest.mock import MagicMock
import services.metering.lambdas.aggregate.handler as agg_mod
from datetime import datetime, timezone

class _FakeDatetime:
    @staticmethod
    def now(tz=None):
        # Fixed time for deterministic invoice_id "YYYY-MM"
        return datetime(2025, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

def _mk_scan_pages():
    # Two scan pages to exercise pagination
    page1 = {"Items": [
        {"tenant_id": "t1", "token_count": 100},
        {"tenant_id": "t2", "token_count": 200},
    ], "LastEvaluatedKey": {"k": "1"}}
    page2 = {"Items": [
        {"tenant_id": "t1", "token_count": 50},
    ]}
    return [page1, page2]

def test_aggregate_creates_invoices_per_tenant(monkeypatch):
    usage_tbl = MagicMock()
    invoices_tbl = MagicMock()

    pages = _mk_scan_pages()
    usage_tbl.scan.side_effect = pages

    # Patch the module to return our MagicMocks
    monkeypatch.setattr(agg_mod, "_get_tables", lambda: (usage_tbl, invoices_tbl))

    # Patch datetime used inside the module so month is deterministic
    monkeypatch.setattr(agg_mod, "datetime", _FakeDatetime)

    resp = agg_mod.handler({}, None)
    assert resp["message"] == "ok"
    assert resp["period"] == "2025-08"
    assert resp["tenants"] == 2

    # We expect two put_item calls: t1 with 150, t2 with 200
    assert invoices_tbl.put_item.call_count == 2
    calls = [kwargs["Item"] for _, kwargs in invoices_tbl.put_item.call_args_list]
    items = {c["tenant_id"]: c for c in calls}
    assert items["t1"]["invoice_id"] == "t1-2025-08"
    assert items["t1"]["tokens"] == "150"
    assert items["t1"]["status"] == "DRAFT"
    assert items["t2"]["invoice_id"] == "t2-2025-08"
    assert items["t2"]["tokens"] == "200"
