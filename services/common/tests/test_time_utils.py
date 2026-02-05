import re
from datetime import datetime, timezone, timedelta
import pytest

from services.common import time_utils


def test_now_utc_returns_datetime():
    result = time_utils.now_utc()
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc


def test_iso_utc_now_format():
    result = time_utils.iso_utc_now()
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)


def test_now_utc_iso_matches_iso_utc_now():
    r1 = time_utils.now_utc_iso()
    r2 = time_utils.iso_utc_now()
    # They should both produce ISO strings with Z suffix
    assert r1.endswith("Z") and r2.endswith("Z")


def test_to_iso_z_roundtrip():
    now = datetime(2025, 9, 25, 12, 0, 0, tzinfo=timezone.utc)
    iso_str = time_utils.to_iso_z(now)
    parsed = time_utils.parse_iso(iso_str)
    # Within 1 second tolerance because of timespec truncation
    assert abs((parsed - now).total_seconds()) < 1


def test_parse_iso_invalid_returns_now(monkeypatch):
    fake_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(time_utils, "now_utc", lambda: fake_now)
    result = time_utils.parse_iso("not-a-timestamp")
    assert result == fake_now


def test_month_key_and_ymd_helpers():
    dt = datetime(2025, 12, 5, tzinfo=timezone.utc)
    assert time_utils.month_key(dt) == "2025-12"
    assert time_utils.ymd(dt) == "2025-12-05"


def test_now_utc_iso_is_alias_of_iso_utc_now():
    r1 = time_utils.now_utc_iso()
    r2 = time_utils.iso_utc_now()
    assert r1 == r2

def test_parse_iso_invalid_string_returns_now(monkeypatch):
    fake_now = datetime(2025, 9, 25, 0, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(time_utils, "now_utc", lambda: fake_now)
    result = time_utils.parse_iso("not-a-timestamp")
    assert isinstance(result, datetime)
    assert result == fake_now

