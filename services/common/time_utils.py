# services/common/time_utils.py
from __future__ import annotations
from datetime import datetime
try:
    # Py 3.12+
    from datetime import UTC
except ImportError:  # Py 3.11 and below
    from datetime import timezone as _tz
    UTC = _tz.utc

def now_utc() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(UTC)

def to_iso_z(dt: datetime, *, timespec: str = "seconds") -> str:
    """Serialize any datetime to ISO-8601 in UTC with trailing 'Z'."""
    # datetime.isoformat(timespec=...) is available on 3.6+
    return dt.astimezone(UTC).isoformat(timespec=timespec).replace("+00:00", "Z")

def iso_utc_now(*, timespec: str = "seconds") -> str:
    """Current UTC timestamp as ISO-8601 with 'Z' suffix."""
    return to_iso_z(now_utc(), timespec=timespec)

# ---- Back-compat (prefer iso_utc_now) ---------------------------------------
def now_utc_iso(z_suffix: bool = True) -> str:
    """DEPRECATED: use iso_utc_now(). Kept for compatibility."""
    # ignore z_suffix; we always return Z-normalized strings
    return iso_utc_now()

def parse_iso(s: str) -> datetime:
    """Parse ISO-8601 strings, including 'Z', into aware UTC datetimes."""
    if not s:
        return now_utc()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return now_utc()

# ---- Convenience helpers -----------------------------------------------------
def month_key(dt: datetime | None = None) -> str:
    """'YYYY-MM' in UTC (useful for tenant-month partition keys)."""
    dt = dt or now_utc()
    return f"{dt.year}-{dt.month:02d}"

def ymd(dt: datetime | None = None) -> str:
    """'YYYY-MM-DD' in UTC."""
    dt = dt or now_utc()
    return dt.date().isoformat()
