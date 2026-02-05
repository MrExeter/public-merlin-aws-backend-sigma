# services/metering/tests/test_log_usage_events.py
import json
from unittest.mock import MagicMock
import services.metering.lambdas.log_usage.handler as log_mod

def test_emit_usage_event_disabled_does_nothing(monkeypatch):
    # Ensure disabled
    monkeypatch.setenv("USAGE_EVENTS_ENABLED", "false")
    mock_events = MagicMock()
    monkeypatch.setattr(log_mod, "events", mock_events)

    item = {"timestamp": "2025-08-25T12:00:00Z", "user_id": "tenant-1", "endpoint": "/x", "token_count": 42}
    log_mod._emit_usage_event(item)

    mock_events.put_events.assert_not_called()

def test_emit_usage_event_enabled_sends_event(monkeypatch):
    monkeypatch.setenv("USAGE_EVENTS_ENABLED", "true")
    mock_events = MagicMock()
    monkeypatch.setattr(log_mod, "events", mock_events)

    item = {"timestamp": "2025-08-25T12:00:00Z", "user_id": "tenant-1", "endpoint": "/x", "token_count": 42}
    log_mod._emit_usage_event(item)

    assert mock_events.put_events.call_count == 1
    entry = mock_events.put_events.call_args.kwargs["Entries"][0]
    # Validate the important bits in the event envelope
    assert entry["Source"] == "baas.metering"
    assert entry["DetailType"] == "UsageEvent"
    detail = json.loads(entry["Detail"])
    assert detail["tenant_id"] == "tenant-1"
    assert detail["service"] == "usage"
    assert detail["action"] == "log"
    assert detail["quantity"] == 42
    assert detail["meta"]["endpoint"] == "/x"
