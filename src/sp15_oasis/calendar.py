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


def expected_hours(day: date) -> int:
    """Hours in one Pacific operating day. Spring-forward is 23, fall-back is 25."""
    nxt = day + timedelta(days=1)
    start = datetime(day.year, day.month, day.day, tzinfo=PT)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=PT)
    # Same-zone subtraction ignores the DST offset change, so compare in UTC.
    elapsed = end.astimezone(UTC) - start.astimezone(UTC)
    return int(elapsed.total_seconds() // 3600)


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


def iter_chunks(start: date, end_inclusive: date, chunk_days: int = CHUNK_DAYS):
    """Yield half-open buckets that overlap the inclusive operating-day range."""
    if end_inclusive < start:
        return
    if chunk_days == CHUNK_DAYS:
        cur = floor_chunk(start)
        while cur <= end_inclusive:
            yield cur, cur + timedelta(days=CHUNK_DAYS)
            cur = cur + timedelta(days=CHUNK_DAYS)
        return
    cur = start
    step = timedelta(days=chunk_days)
    while cur <= end_inclusive:
        nxt = min(cur + step, end_inclusive + timedelta(days=1))
        yield cur, nxt
        cur = nxt


# How many calendar days before the operating day the value was knowable.
# DAM is the day-ahead publication (D-1). 2DA is D-2. 7DA is D-7.
_DAY_LEAD = {"DAM": 1, "2DA": 2, "7DA": 7, "RUC": 1}
# Real-time markets are issued inside the hour. The date is the Pacific date
# of (interval start minus this many minutes), so the first interval of a day
# can carry the previous calendar date.
_MINUTE_LEAD = {"HASP": 75, "RTPD": 30, "RTD": 5, "RTM": 5}


def issued_on(opr_dt: date, market: str, interval_start: str | None = None) -> date:
    """Forecast date for a value that applies to operating day ``opr_dt``.

    Actuals are not forecasts: the date is the operating day itself.
    """
    market = (market or "DAM").upper()
    if market in _DAY_LEAD:
        return opr_dt - timedelta(days=_DAY_LEAD[market])
    if market == "ACTUAL":
        return opr_dt
    minutes = _MINUTE_LEAD.get(market)
    moment = _parse_interval(interval_start) if minutes and interval_start else None
    if moment is not None and minutes is not None:
        return (moment - timedelta(minutes=minutes)).astimezone(PT).date()
    return opr_dt


def _parse_interval(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"日期要用 YYYY-MM-DD，收到 {value!r}") from exc
