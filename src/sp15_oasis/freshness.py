"""Whether the latest published operating day is complete enough to stop syncing.

Shadow prices are left out: CAISO only publishes them for binding hours, so a
quiet hour is not a missing download. The May 2026 ATC hole is a source gap,
not a failed sync.
"""

from __future__ import annotations

from datetime import date

from .calendar import expected_hours
from .catalog import node_ids, tie_ids
from .db import MissingDatabase, connect

LMP_TYPES = ("LMP", "MCC", "MCE", "MCL", "MGHG")
AS_TYPES = ("RU", "RD", "SR", "NR")
AS_REQUIREMENTS = (
    ("RU", "RU_REQ_MAX_MW"),
    ("RU", "RU_REQ_MIN_MW"),
    ("RD", "RD_REQ_MAX_MW"),
    ("RD", "RD_REQ_MIN_MW"),
    ("SR", "SP_REQ_MAX_MW"),
    ("SR", "SP_REQ_MIN_MW"),
    ("NR", "NS_REQ_MAX_MW"),
    ("NR", "NS_REQ_MIN_MW"),
)
TIE_DIRECTIONS = ("I", "E")
# OASIS published prices for these days and returned no ATC or usage rows.
ATC_SOURCE_HOLE = (date(2026, 5, 1), date(2026, 5, 4))


def day_gaps(day: date) -> list[str]:
    """Short Chinese descriptions of what a published operating day is missing."""
    hours = expected_hours(day)
    try:
        conn = connect(write=False)
    except MissingDatabase:
        return [f"还没有本地库，运行日 {day.isoformat()} 没有数据"]
    try:
        gaps: list[str] = []
        gaps.extend(
            _series_gap(
                "日前电价",
                _counts(conn, "SELECT node, lmp_type, COUNT(DISTINCT interval_start) FROM dam_lmp WHERE opr_dt = ? GROUP BY 1, 2", day),
                [(node, kind) for node in node_ids() for kind in LMP_TYPES],
                hours,
            )
        )
        gaps.extend(
            _series_gap(
                "辅助服务价格",
                _counts(conn, "SELECT anc_type, '', COUNT(DISTINCT interval_start) FROM as_price WHERE opr_dt = ? GROUP BY 1", day),
                [(kind, "") for kind in AS_TYPES],
                hours,
            )
        )
        gaps.extend(
            _series_gap(
                "辅助服务需求",
                _counts(
                    conn,
                    "SELECT anc_type, xml_data_item, COUNT(DISTINCT interval_start) FROM as_requirement WHERE opr_dt = ? GROUP BY 1, 2",
                    day,
                ),
                list(AS_REQUIREMENTS),
                hours,
            )
        )
        if not _in_atc_hole(day):
            tie_keys = [(tie, direction) for tie in tie_ids() for direction in TIE_DIRECTIONS]
            tie_sql = (
                "SELECT ti_id, ti_direction, COUNT(DISTINCT interval_start) "
                "FROM {table} WHERE opr_dt = ? GROUP BY 1, 2"
            )
            gaps.extend(_series_gap("联络线 ATC", _counts(conn, tie_sql.format(table="tie_atc"), day), tie_keys, hours))
            gaps.extend(_series_gap("断面使用", _counts(conn, tie_sql.format(table="tie_usage"), day), tie_keys, hours))
        return [gap for gap in gaps if gap]
    finally:
        conn.close()


def _in_atc_hole(day: date) -> bool:
    start, end = ATC_SOURCE_HOLE
    return start <= day <= end


def _counts(conn, sql: str, day: date) -> dict[tuple[str, str], int]:
    found: dict[tuple[str, str], int] = {}
    for key_a, key_b, count in conn.execute(sql, (day.isoformat(),)):
        found[(str(key_a), str(key_b))] = int(count)
    return found


def _series_gap(
    label: str,
    found: dict[tuple[str, str], int],
    required: list[tuple[str, str]],
    hours: int,
) -> list[str]:
    short = [key for key in required if found.get(key, 0) < hours]
    if not short:
        return []
    worst = min(found.get(key, 0) for key in short)
    if worst == 0 and len(short) == len(required):
        return [f"没有{label}"]
    return [f"{label} {worst}/{hours} 小时，缺 {len(short)} 项"]
