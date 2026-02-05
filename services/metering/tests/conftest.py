# services/metering/tests/conftest.py
import pytest

@pytest.fixture(autouse=True)
def metering_env(monkeypatch):
    # Align with your aggregate handler's env lookups
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-1")
    monkeypatch.setenv("USAGE_LOGS_TABLE_NAME", "UsageLogs-dev")
    monkeypatch.setenv("USAGE_INVOICES_TABLE_NAME", "UsageInvoices-dev")
