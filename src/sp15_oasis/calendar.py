"""Pacific operating days and the fixed 31-day download grid."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
UTC = ZoneInfo("UTC")

# Live OASIS keeps about 39 months. August 2023 is the start of that window
# for a sync run in November 2026. Earlier days come back empty and are cached
# as empty so they are not requested again.
RETENTION_FLOOR = date(2023, 8, 1)
CHUNK_DAYS = 31


def today_pt() -> date:
    return datetime.now(PT).date()


def trading_bounds(start: date, end: date) -> tuple[str, str]:
    """Turn a half-open operating-day range into OASIS GMT parameters.

    ``end`` is exclusive. Midnight Pacific is converted with the offset that
    was actually in effect, so a chunk that crosses the November fallback or
    the March spring-forward stays aligned to CAISO operating days.
    """
    if end <= start:
        raise ValueError(f"empty window {start} .. {end}")
    start_local = datetime(start.year, start.month, start.day, tzinfo=PT)
    end_local = datetime(end.year, end.month, end.day, tzinfo=PT)
    return _gmt(start_local), _gmt(end_local)


def _gmt(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H:%M-0000")


def floor_chunk(day: date) -> date:
    """First operating day of the 31-day bucket that contains ``day``."""
    delta = (day - RETENTION_FLOOR).days
    if delta >= 0:
        return RETENTION_FLOOR + timedelta(days=(delta // CHUNK_DAYS) * CHUNK_DAYS)
    steps = (-delta + CHUNK_DAYS - 1) // CHUNK_DAYS
    return RETENTION_FLOOR - timedelta(days=steps * CHUNK_DAYS)


def iter_chunks(start: date, end_inclusive: date):
    """Yield half-open buckets that overlap the inclusive operating-day range."""
    if end_inclusive < start:
        return
    cur = floor_chunk(start)
    while cur <= end_inclusive:
        yield cur, cur + timedelta(days=CHUNK_DAYS)
        cur = cur + timedelta(days=CHUNK_DAYS)


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"日期要用 YYYY-MM-DD，收到 {value!r}") from exc
