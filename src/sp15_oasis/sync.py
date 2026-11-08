"""Download the live OASIS window into the local database.

Requests are serial and at least seven seconds apart. CAISO's acceptable-use
policy asks callers to back off, and a parallel sync from the whole team will
get the IP blocked. Sync once and copy data/sp15.sqlite if several people need
the same snapshot.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from .calendar import RETENTION_FLOOR, iter_chunks, today_pt, trading_bounds
from .catalog import node_ids, tie_ids
from .db import chunk_status, connect, mark_chunk, upsert
from .oasis import OasisClient, OasisError
from .parse import (
    normalize_as_price,
    normalize_as_requirement,
    normalize_atc,
    normalize_intertie_shadow,
    normalize_lmp,
    normalize_nomogram,
    normalize_usage,
)

Normalize = Callable[[list[dict]], list[dict]]
Params = Callable[[date, date, list[str]], dict[str, str]]


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


@dataclass(frozen=True)
class Spec:
    name: str
    table: str
    sparse: bool
    params: Params
    normalize: Normalize
    values: tuple[str, ...]
    split_key: str | None


def _bounds(start: date, end: date) -> dict[str, str]:
    start_gmt, end_gmt = trading_bounds(start, end)
    return {"startdatetime": start_gmt, "enddatetime": end_gmt, "resultformat": "6"}


def _lmp(start: date, end: date, values: list[str]) -> dict[str, str]:
    return {
        "queryname": "PRC_LMP",
        "version": "12",
        "market_run_id": "DAM",
        "node": ",".join(values),
        **_bounds(start, end),
    }


def _as_price(start: date, end: date, values: list[str]) -> dict[str, str]:
    del values
    return {
        "queryname": "PRC_AS",
        "version": "12",
        "market_run_id": "DAM",
        "anc_type": "ALL",
        "anc_region": "AS_SP26",
        **_bounds(start, end),
    }


def _as_req(start: date, end: date, values: list[str]) -> dict[str, str]:
    del values
    return {
        "queryname": "AS_REQ",
        "version": "1",
        "market_run_id": "DAM",
        "anc_type": "ALL",
        "anc_region": "AS_SP26",
        **_bounds(start, end),
    }


def _atc(start: date, end: date, values: list[str]) -> dict[str, str]:
    return {
        "queryname": "TRNS_ATC",
        "version": "1",
        "market_run_id": "DAM",
        "ti_id": ",".join(values),
        "ti_direction": "ALL",
        **_bounds(start, end),
    }


def _usage(start: date, end: date, values: list[str]) -> dict[str, str]:
    return {
        "queryname": "TRNS_USAGE",
        "version": "1",
        "market_run_id": "DAM",
        "ti_id": ",".join(values),
        "ti_direction": "ALL",
        **_bounds(start, end),
    }


def _intertie(start: date, end: date, values: list[str]) -> dict[str, str]:
    del values
    return {
        "queryname": "PRC_CNSTR",
        "version": "1",
        "market_run_id": "DAM",
        "ti_id": "ALL",
        **_bounds(start, end),
    }


def _nomogram(start: date, end: date, values: list[str]) -> dict[str, str]:
    del values
    return {
        "queryname": "PRC_NOMOGRAM",
        "version": "1",
        "market_run_id": "DAM",
        "nomogram_id": "ALL",
        **_bounds(start, end),
    }


SPECS: tuple[Spec, ...] = (
    Spec("dam_lmp", "dam_lmp", False, _lmp, normalize_lmp, tuple(node_ids()), "NODE"),
    Spec("as_price", "as_price", False, _as_price, normalize_as_price, (), None),
    Spec("as_requirement", "as_requirement", False, _as_req, normalize_as_requirement, (), None),
    Spec("intertie_shadow", "intertie_shadow", True, _intertie, normalize_intertie_shadow, (), None),
    Spec("nomogram_shadow", "nomogram_shadow", True, _nomogram, normalize_nomogram, (), None),
    Spec("tie_atc", "tie_atc", False, _atc, normalize_atc, tuple(tie_ids()), "TI_ID"),
    Spec("tie_usage", "tie_usage", False, _usage, normalize_usage, tuple(tie_ids()), "TI_ID"),
)

SPEC_BY_NAME = {spec.name: spec for spec in SPECS}


def sync_all(
    start: date | None = None,
    end: date | None = None,
    datasets: list[str] | None = None,
    sleep_seconds: float = 7.0,
    refresh: bool = False,
) -> None:
    start = start or RETENTION_FLOOR
    end = end or today_pt()
    if end < start:
        raise ValueError(f"结束日 {end} 早于开始日 {start}")
    chosen = [SPEC_BY_NAME[name] for name in datasets] if datasets else list(SPECS)
    unknown = [name for name in (datasets or []) if name not in SPEC_BY_NAME]
    if unknown:
        raise ValueError(f"未知数据集 {unknown}。可选：{', '.join(SPEC_BY_NAME)}")
    client = OasisClient(sleep_seconds=sleep_seconds)
    conn = connect(write=True)
    try:
        for spec in chosen:
            _sync_spec(conn, client, spec, start, end, refresh)
    finally:
        conn.close()


def _sync_spec(conn, client: OasisClient, spec: Spec, start: date, end: date, refresh: bool) -> None:
    today = today_pt()
    failures = 0
    skipped = 0
    for chunk_start, chunk_end in iter_chunks(start, end):
        status = chunk_status(conn, spec.name, chunk_start.isoformat(), chunk_end.isoformat())
        closed = chunk_end <= today
        if status in {"ok", "empty"} and closed and not refresh:
            skipped += 1
            continue
        log(f"{spec.name} {chunk_start} .. {chunk_end} 下载中")
        try:
            raw = _fetch_window(client, spec, chunk_start, chunk_end)
        except OasisError as exc:
            failures += 1
            log(f"  失败：{exc}")
            with conn:
                mark_chunk(
                    conn,
                    spec.name,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                    "error",
                    0,
                    str(exc),
                )
            if failures >= 3:
                log(f"{spec.name} 连续失败 3 次，先停。稍后重跑 sync 会从失败的块继续。")
                break
            continue
        failures = 0
        stored = spec.normalize(raw)
        with conn:
            count = upsert(conn, spec.table, stored)
            mark_chunk(
                conn,
                spec.name,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
                "ok" if stored else "empty",
                count,
                "",
            )
        log(f"  写入 {count} 行")
    if skipped:
        log(f"{spec.name} 跳过已完成的 {skipped} 块。加 --refresh 可重下。")


def _fetch_window(client: OasisClient, spec: Spec, start: date, end: date) -> list[dict]:
    rows = _fetch_values(client, spec, start, end, list(spec.values))
    if rows is not None:
        return rows
    return _split_dates(client, spec, start, end)


def _split_dates(client: OasisClient, spec: Spec, start: date, end: date) -> list[dict]:
    """Break up a window whose zip had no CSV.

    A last operating day with no rows means the whole window is outside the
    live archive, except for sparse constraint reports: those can be quiet on
    the first or last day and still have rows in between. If both ends are
    empty, the window is treated as empty.
    """
    span = (end - start).days
    if span <= 1:
        return []
    values = list(spec.values)
    tail = _fetch_values(client, spec, end - timedelta(days=1), end, values)
    if not tail:
        if not spec.sparse:
            return []
        head = _fetch_values(client, spec, start, start + timedelta(days=1), values)
        if not head:
            return []
    mid = start + timedelta(days=span // 2)
    if not (start < mid < end):
        return []
    log(f"  {spec.name} {start}..{end} 整包没有数据，拆成两段")
    left = _fetch_window(client, spec, start, mid)
    right = _fetch_window(client, spec, mid, end)
    return left + right


def _fetch_values(
    client: OasisClient,
    spec: Spec,
    start: date,
    end: date,
    values: list[str],
) -> list[dict] | None:
    rows = client.fetch_csv(spec.params(start, end, values))
    if rows is None or spec.split_key is None or len(values) <= 1:
        return rows
    seen = {row.get(spec.split_key, "") for row in rows}
    seen.discard("")
    # A comma-separated id list that comes back as a single id was truncated.
    if len(seen) <= 1 and len(values) > 1:
        log(f"  {spec.name} 只返回了 {seen or '空'}，改成两批 id 再请求")
        mid = len(values) // 2
        left = _fetch_values(client, spec, start, end, values[:mid])
        right = _fetch_values(client, spec, start, end, values[mid:])
        if left is None and right is None:
            return None
        return (left or []) + (right or [])
    missing = [value for value in values if value not in seen]
    if missing:
        log(f"  {spec.name} 这一包没有这些 id（可能当时还不存在）：{', '.join(missing)}")
    return rows
