"""Read-only queries used by the MCP tools and the CSV export."""

from __future__ import annotations

import json
import re
import sqlite3

from .catalog import HUB, MAJOR_TIES, NODES, catalog_payload, node_ids, tie_ids, tie_prefix
from .db import TABLES, MissingDatabase, connect

_NODE_BY_ID = {node.node_id: node for node in NODES}
_HUB_TYPES = ("LMP", "MCC", "MCE", "MCL", "MGHG")
_SAFE_ID = re.compile(r"[A-Za-z0-9_\-]+")
_SAFE_LABEL = re.compile(r"[A-Za-z0-9_ \-]+")
_SAFE_TYPE = re.compile(r"[A-Z0-9_]+")


def list_catalog() -> dict:
    payload = catalog_payload()
    try:
        conn = connect()
    except MissingDatabase as exc:
        payload["database"] = {"ready": False, "detail": str(exc)}
        return payload
    try:
        payload["database"] = {"ready": True, **_coverage(conn)}
    finally:
        conn.close()
    return payload


def dataset_coverage() -> dict:
    conn = connect()
    try:
        return _coverage(conn)
    finally:
        conn.close()


def query_dam_prices(
    start: str,
    end: str,
    node: str = HUB,
    component: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Day-ahead prices in USD/MWh. ``end`` is an inclusive operating day."""
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    nodes = _nodes(node)
    component = component.upper()
    conn = connect()
    try:
        if component == "ALL":
            types = _lmp_types(conn)
            columns = ", ".join(
                f"MAX(CASE WHEN lmp_type = '{lmp_type}' THEN value END) AS {lmp_type}"
                for lmp_type in types
            )
            where, params = _node_where(nodes, start_day, end_day)
            total = conn.execute(
                f"SELECT COUNT(*) FROM (SELECT 1 FROM dam_lmp WHERE {where} GROUP BY opr_dt, opr_hr, node)",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT opr_dt, MIN(issued_on) AS issued_on, opr_hr,
                       MIN(interval_start) AS interval_start_utc,
                       MIN(interval_end) AS interval_end_utc,
                       node, {columns}
                FROM dam_lmp
                WHERE {where}
                GROUP BY opr_dt, opr_hr, node
                ORDER BY opr_dt, opr_hr, node
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        else:
            if not _SAFE_TYPE.fullmatch(component):
                raise ValueError(f"未知电价分量 {component}")
            where, params = _node_where(nodes, start_day, end_day)
            where += " AND lmp_type = ?"
            params = [*params, component]
            total = conn.execute(f"SELECT COUNT(*) FROM dam_lmp WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT issued_on, opr_dt, opr_hr, interval_start AS interval_start_utc,
                       interval_end AS interval_end_utc, node, lmp_type AS component, value AS usd_per_mwh
                FROM dam_lmp
                WHERE {where}
                ORDER BY opr_dt, opr_hr, node
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return _page(
            rows,
            total=total,
            limit=limit,
            offset=offset,
            capped=capped,
            unit="USD/MWh",
            operating_day_end_inclusive=True,
        )
    finally:
        conn.close()


def query_ancillary(
    start: str,
    end: str,
    kind: str = "price",
    anc_type: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    table = {"price": "as_price", "requirement": "as_requirement", "result": "as_result"}.get(kind)
    if table is None:
        raise ValueError("kind 要用 price、requirement 或 result")
    unit = {"price": "USD/MW", "requirement": "MW", "result": "MW；UOM 为 2 时 value 是美元成本"}[kind]
    columns = "opr_dt, opr_hr, interval_start AS interval_start_utc, anc_type, anc_region, xml_data_item, value"
    if kind == "result":
        columns += ", result_type, uom"
    where = "anc_region = 'AS_SP26' AND opr_dt >= ? AND opr_dt <= ?"
    params: list = [start_day, end_day]
    if anc_type:
        if not _SAFE_TYPE.fullmatch(anc_type.upper()):
            raise ValueError(f"未知辅助服务类型 {anc_type}")
        where += " AND anc_type = ?"
        params.append(anc_type.upper())
    conn = connect()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT {columns}
            FROM {table}
            WHERE {where}
            ORDER BY opr_dt, opr_hr, anc_type, xml_data_item
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return _page(
            rows,
            total=total,
            limit=limit,
            offset=offset,
            capped=capped,
            unit=unit,
            region="AS_SP26",
        )
    finally:
        conn.close()


def query_load(
    start: str,
    end: str,
    market: str = "DAM",
    tac_area: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Hourly load forecast or actual demand, in MW."""
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    market = market.upper()
    if market == "PEAK":
        return _query_rows(
            "load_peak",
            "opr_dt, opr_hr, interval_start AS interval_start_utc, tac_area, value",
            start_day,
            end_day,
            limit,
            offset,
            capped,
            extra_filters=[("tac_area", tac_area)],
            unit="MW",
            market="PEAK",
        )
    if market not in {"DAM", "2DA", "7DA", "ACTUAL", "ALL"}:
        raise ValueError("market 要用 DAM、2DA、7DA、ACTUAL、PEAK 或 ALL")
    filters = [] if market == "ALL" else [("market_run_id", market)]
    filters.append(("tac_area", tac_area))
    return _query_rows(
        "load",
        "opr_dt, opr_hr, interval_start AS interval_start_utc, market_run_id, tac_area, xml_data_item, label, value",
        start_day,
        end_day,
        limit,
        offset,
        capped,
        extra_filters=filters,
        unit="MW",
        market=market,
    )


def query_renewables(
    start: str,
    end: str,
    market: str = "ACTUAL",
    trading_hub: str = "SP15",
    renewable_type: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Wind and solar forecast or actual generation. SUMMARY is the ISO-wide hourly total."""
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    market = market.upper()
    if market == "SUMMARY":
        return _query_rows(
            "wind_solar_summary",
            "opr_dt, opr_hr, interval_start AS interval_start_utc, market_run_id, data_item, value",
            start_day,
            end_day,
            limit,
            offset,
            capped,
            extra_filters=[],
            unit="MW",
            market="SUMMARY",
        )
    if market not in {"DAM", "ACTUAL", "ALL"}:
        raise ValueError("market 要用 DAM、ACTUAL、SUMMARY 或 ALL")
    filters = [] if market == "ALL" else [("market_run_id", market)]
    filters.append(("trading_hub", trading_hub))
    filters.append(("renewable_type", renewable_type))
    return _query_rows(
        "renewable",
        "opr_dt, opr_hr, interval_start AS interval_start_utc, market_run_id, trading_hub, renewable_type, value",
        start_day,
        end_day,
        limit,
        offset,
        capped,
        extra_filters=filters,
        unit="MW",
        market=market,
    )


def query_fuel(
    start: str,
    end: str,
    fuel_region_id: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    return _query_rows(
        "fuel_price",
        "opr_dt, opr_hr, interval_start AS interval_start_utc, fuel_region_id, value",
        start_day,
        end_day,
        limit,
        offset,
        capped,
        extra_filters=[("fuel_region_id", fuel_region_id)],
        unit="USD/mmBtu",
    )


def query_ghg(start: str, end: str, limit: int = 200, offset: int = 0) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    return _query_rows(
        "ghg_allowance",
        "opr_dt, interval_start AS interval_start_utc, interval_end AS interval_end_utc, value",
        start_day,
        end_day,
        limit,
        offset,
        capped,
        extra_filters=[],
        unit="USD/tCO2",
    )


def query_system_schedule(
    start: str,
    end: str,
    tac_zone: str = "TAC_SOUTH",
    schedule: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    return _query_rows(
        "system_schedule",
        "opr_dt, opr_hr, interval_start AS interval_start_utc, tac_zone, schedule, xml_data_item, value",
        start_day,
        end_day,
        limit,
        offset,
        capped,
        extra_filters=[("tac_zone", tac_zone), ("schedule", schedule)],
        unit="MW",
        market="DAM",
    )


def _query_rows(
    table: str,
    columns: str,
    start_day: str,
    end_day: str,
    limit: int,
    offset: int,
    capped: bool,
    *,
    extra_filters: list[tuple[str, str]],
    unit: str,
    **meta,
) -> dict:
    where = ["opr_dt >= ?", "opr_dt <= ?"]
    params: list = [start_day, end_day]
    for column, value in extra_filters:
        if not value or value.upper() == "ALL":
            continue
        if not _SAFE_LABEL.fullmatch(value):
            raise ValueError(f"不能识别的筛选值 {value}")
        where.append(f"{column} = ?")
        params.append(value)
    clause = " AND ".join(where)
    order = "opr_dt, opr_hr" if "opr_hr" in columns else "opr_dt"
    conn = connect()
    try:
        _require_table(conn, table)
        total = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT issued_on, {columns} FROM {table} WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return _page(rows, total=total, limit=limit, offset=offset, capped=capped, unit=unit, **meta)
    finally:
        conn.close()


def _require_table(conn: sqlite3.Connection, table: str) -> None:
    found = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if found is None:
        raise ValueError(f"还没有 {table}。先运行 sync，把这张新表补进本地库。")


def query_tie_atc(
    start: str,
    end: str,
    ti_id: str = "",
    direction: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    return _query_ties(
        "tie_atc",
        start,
        end,
        ti_id,
        direction,
        limit,
        offset,
        "value AS atc_mw",
        "MW",
    )


def query_tie_usage(
    start: str,
    end: str,
    ti_id: str = "",
    direction: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    columns = """
        atc_mw, as_import_mw, ene_import_mw, cbm_mw, constraint_mw,
        mkt_xfer_cap_mw, otc_mw, trm_mw, trm_fto_mw, trm_spi_mw, trm_uf_mw,
        ttc_mw, useage_mw, extra_json
    """
    return _query_ties("tie_usage", start, end, ti_id, direction, limit, offset, columns, "MW")


def query_shadow_prices(
    start: str,
    end: str,
    kind: str = "nomogram",
    region: str = "related",
    name_contains: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    if region not in {"sp15", "path15", "related", "all"}:
        raise ValueError("region 要用 sp15、path15、related 或 all")
    conn = connect()
    try:
        if kind == "nomogram":
            where = "opr_dt >= ? AND opr_dt <= ?"
            params: list = [start_day, end_day]
            if region == "sp15":
                where += " AND region_tag = 'sp15'"
            elif region == "path15":
                where += " AND region_tag = 'path15'"
            elif region == "related":
                where += " AND region_tag IN ('sp15', 'path15')"
            if name_contains:
                where += " AND UPPER(nomogram_id) LIKE ? ESCAPE '\\'"
                params.append(_like(name_contains))
            total = conn.execute(
                f"SELECT COUNT(*) FROM nomogram_shadow WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT issued_on, opr_dt, opr_hr, interval_start AS interval_start_utc,
                       nomogram_id, constraint_cause, value AS usd_per_mwh, region_tag
                FROM nomogram_shadow
                WHERE {where}
                ORDER BY opr_dt, opr_hr, nomogram_id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        elif kind == "intertie":
            where = "opr_dt >= ? AND opr_dt <= ?"
            params = [start_day, end_day]
            if region in {"sp15", "related"}:
                where += " AND sp15_related = 1"
            elif region == "path15":
                where += " AND 1 = 0"
            if name_contains:
                where += " AND UPPER(ti_id) LIKE ? ESCAPE '\\'"
                params.append(_like(name_contains))
            total = conn.execute(
                f"SELECT COUNT(*) FROM intertie_shadow WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT issued_on, opr_dt, opr_hr, interval_start AS interval_start_utc,
                       ti_id, ti_direction, constraint_cause, value AS usd_per_mwh, sp15_related
                FROM intertie_shadow
                WHERE {where}
                ORDER BY opr_dt, opr_hr, ti_id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        else:
            raise ValueError("kind 要用 nomogram 或 intertie")
        return _page(
            rows,
            total=total,
            limit=limit,
            offset=offset,
            capped=capped,
            unit="USD/MWh",
            shadow_null_means="未返回的小时表示该约束这一小时没有被披露为绑定，不是 0。",
        )
    finally:
        conn.close()


def training_panel(
    start: str,
    end: str,
    ties: str = "MAJOR",
    limit: int = 168,
    offset: int = 0,
) -> dict:
    """One row per operating hour for the SP15 hub, with boundary features beside it."""
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit, cap=5000)
    _offset(offset)
    selected = _ties(ties)
    conn = connect()
    try:
        total = conn.execute(
            """
            SELECT COUNT(*) FROM dam_lmp
            WHERE node = ? AND lmp_type = 'LMP' AND opr_dt >= ? AND opr_dt <= ?
            """,
            (HUB, start_day, end_day),
        ).fetchone()[0]
        spine = conn.execute(
            """
            SELECT issued_on, opr_dt, opr_hr, interval_start, interval_end
            FROM dam_lmp
            WHERE node = ? AND lmp_type = 'LMP' AND opr_dt >= ? AND opr_dt <= ?
            ORDER BY opr_dt, opr_hr
            LIMIT ? OFFSET ?
            """,
            (HUB, start_day, end_day, limit, offset),
        ).fetchall()
        if not spine:
            return _page([], total=total, limit=limit, offset=offset, capped=capped, unit="mixed")
        first, last = spine[0]["opr_dt"], spine[-1]["opr_dt"]
        prices = _index_prices(conn, first, last)
        ancillary = _index_ancillary(conn, first, last)
        path26 = _index_max(
            conn,
            """
            SELECT opr_dt, opr_hr, MAX(value) AS value
            FROM nomogram_shadow
            WHERE opr_dt >= ? AND opr_dt <= ?
              AND UPPER(nomogram_id) LIKE '%MIDWAY%'
              AND UPPER(nomogram_id) LIKE '%VINCENT%'
              AND UPPER(nomogram_id) LIKE '%500%'
            GROUP BY opr_dt, opr_hr
            """,
            (first, last),
        )
        path15 = _index_max(
            conn,
            """
            SELECT opr_dt, opr_hr, MAX(value) AS value
            FROM nomogram_shadow
            WHERE opr_dt >= ? AND opr_dt <= ?
              AND UPPER(nomogram_id) LIKE '%GATES%'
              AND UPPER(nomogram_id) LIKE '%MIDWAY%'
              AND UPPER(nomogram_id) LIKE '%500%'
            GROUP BY opr_dt, opr_hr
            """,
            (first, last),
        )
        branch = _index_max(
            conn,
            """
            SELECT opr_dt, opr_hr, MAX(value) AS value
            FROM nomogram_shadow
            WHERE opr_dt >= ? AND opr_dt <= ? AND region_tag = 'sp15'
            GROUP BY opr_dt, opr_hr
            """,
            (first, last),
        )
        intertie = _index_direction_max(conn, first, last)
        flows = _index_flows(conn, first, last, selected)
        hub_types = list(_HUB_TYPES)
        hub_types.extend(
            sorted(
                {
                    lmp_type
                    for (_hour, node_id, lmp_type) in prices
                    if node_id == HUB and lmp_type not in _HUB_TYPES
                }
            )
        )
        anc_columns = sorted({column for items in ancillary.values() for _, column, _ in items})
        built = []
        for hour in spine:
            key = (hour["opr_dt"], hour["opr_hr"])
            row: dict = {
                "opr_dt": hour["opr_dt"],
                "issued_on": hour["issued_on"],
                "opr_hr": hour["opr_hr"],
                "interval_start_utc": hour["interval_start"],
                "interval_end_utc": hour["interval_end"],
            }
            for lmp_type in hub_types:
                row[f"sp15_{lmp_type.lower()}"] = prices.get((key, HUB, lmp_type))
            for node in NODES:
                if node.node_id == HUB:
                    continue
                row[f"{node.prefix}_lmp"] = prices.get((key, node.node_id, "LMP"))
                row[f"{node.prefix}_mcc"] = prices.get((key, node.node_id, "MCC"))
            for column in anc_columns:
                row[column] = None
            for _anc_type, column, value in ancillary.get(key, []):
                row[column] = value
            row["path26_shadow"] = path26.get(key)
            row["path15_shadow"] = path15.get(key)
            row["sp15_branch_shadow_max"] = branch.get(key)
            row["sp15_intertie_shadow_i"] = intertie.get((key, "I"))
            row["sp15_intertie_shadow_e"] = intertie.get((key, "E"))
            for ti_id in selected:
                prefix = tie_prefix(ti_id)
                pair = flows.get((key, ti_id), {})
                row[f"{prefix}_atc_i"] = pair.get("atc_i")
                row[f"{prefix}_atc_e"] = pair.get("atc_e")
                row[f"{prefix}_ene_i"] = pair.get("ene_i")
                row[f"{prefix}_ene_e"] = pair.get("ene_e")
            built.append(row)
        return _page(
            built,
            total=total,
            limit=limit,
            offset=offset,
            capped=capped,
            unit="USD/MWh for prices and shadows, MW for atc and ene",
            shadow_null_means="path26_shadow、path15_shadow、sp15_branch_shadow_max、sp15_intertie_shadow_* 为空表示该小时没有披露绑定约束，不是 0。",
            direction="列名以 _i 结尾是进口到 CAISO，_e 是出口。",
            ties=selected,
        )
    finally:
        conn.close()


def query_sql(sql: str, limit: int = 200) -> dict:
    statement = _guard_sql(sql)
    limit, capped = _limit(limit, cap=1000)
    wrapped = f"SELECT * FROM ({statement}) AS query_result LIMIT ?"
    conn = connect()
    try:
        conn.execute("PRAGMA query_only=ON")
        try:
            cursor = conn.execute(wrapped, (limit,))
        except sqlite3.Error as exc:
            raise ValueError(f"查询没有执行：{exc}") from exc
        names = [column[0] for column in cursor.description or []]
        raw = cursor.fetchall()
        rows = [dict(zip(names, tuple(row))) for row in raw]
        return {
            "meta": _meta(returned=len(rows), limit=limit, limit_capped=capped, read_only=True),
            "columns": names,
            "rows": rows,
        }
    finally:
        conn.close()


def _coverage(conn: sqlite3.Connection) -> dict:
    tables = {
        "dam_lmp_sp15_hub": (
            "dam_lmp",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) "
            "FROM dam_lmp WHERE node = ? AND lmp_type = 'LMP'",
            (HUB,),
        ),
        "dam_lmp_rows": (
            "dam_lmp",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM dam_lmp",
            (),
        ),
        "as_price": (
            "as_price",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM as_price",
            (),
        ),
        "as_requirement": (
            "as_requirement",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM as_requirement",
            (),
        ),
        "tie_atc": (
            "tie_atc",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM tie_atc",
            (),
        ),
        "tie_usage": (
            "tie_usage",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM tie_usage",
            (),
        ),
        "intertie_shadow": (
            "intertie_shadow",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM intertie_shadow",
            (),
        ),
        "nomogram_shadow": (
            "nomogram_shadow",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM nomogram_shadow",
            (),
        ),
        "load": (
            "load",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM load",
            (),
        ),
        "load_peak": (
            "load_peak",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM load_peak",
            (),
        ),
        "renewable": (
            "renewable",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM renewable",
            (),
        ),
        "wind_solar_summary": (
            "wind_solar_summary",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM wind_solar_summary",
            (),
        ),
        "fuel_price": (
            "fuel_price",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM fuel_price",
            (),
        ),
        "ghg_allowance": (
            "ghg_allowance",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM ghg_allowance",
            (),
        ),
        "as_result": (
            "as_result",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM as_result",
            (),
        ),
        "system_schedule": (
            "system_schedule",
            "SELECT COUNT(*), MIN(opr_dt), MAX(opr_dt), COUNT(DISTINCT opr_dt) FROM system_schedule",
            (),
        ),
    }
    present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    coverage = {}
    for name, (table, sql, params) in tables.items():
        if table not in present:
            coverage[name] = {
                "rows": 0,
                "first_operating_day": None,
                "last_operating_day": None,
                "distinct_days": 0,
            }
            continue
        count, first, last, days = conn.execute(sql, params).fetchone()
        coverage[name] = {
            "rows": count,
            "first_operating_day": first,
            "last_operating_day": last,
            "distinct_days": days,
        }
    chunks = [
        dict(row)
        for row in conn.execute(
            """
            SELECT dataset, status, COUNT(*) AS chunks, COALESCE(SUM(rows), 0) AS rows,
                   MIN(chunk_start) AS first_chunk, MAX(chunk_end) AS last_chunk_exclusive
            FROM sync_chunk
            GROUP BY dataset, status
            ORDER BY dataset, status
            """
        )
    ]
    return {"tables": coverage, "sync_chunks": chunks, "queryable_tables": sorted(TABLES)}


def _index_prices(conn, first: str, last: str) -> dict:
    found = {}
    rows = conn.execute(
        """
        SELECT opr_dt, opr_hr, node, lmp_type, value
        FROM dam_lmp
        WHERE opr_dt >= ? AND opr_dt <= ? AND node IN ({})
        """.format(",".join("?" for _ in node_ids())),
        (first, last, *node_ids()),
    )
    for row in rows:
        found[(row["opr_dt"], row["opr_hr"]), row["node"], row["lmp_type"]] = row["value"]
    return found


def _index_ancillary(conn, first: str, last: str) -> dict:
    """Map an hour to a list of (anc_type, column, value) so the panel stays wide."""
    found: dict[tuple, list] = {}
    prices = conn.execute(
        """
        SELECT opr_dt, opr_hr, anc_type, xml_data_item, value
        FROM as_price
        WHERE anc_region = 'AS_SP26' AND opr_dt >= ? AND opr_dt <= ?
        """,
        (first, last),
    )
    for row in prices:
        if row["xml_data_item"] and not str(row["xml_data_item"]).endswith("CLR_PRC"):
            continue
        column = f"as_sp26_{row['anc_type'].lower()}"
        found.setdefault((row["opr_dt"], row["opr_hr"]), []).append(
            (row["anc_type"], column, row["value"])
        )
    requirements = conn.execute(
        """
        SELECT opr_dt, opr_hr, anc_type, xml_data_item, value
        FROM as_requirement
        WHERE anc_region = 'AS_SP26' AND opr_dt >= ? AND opr_dt <= ?
        """,
        (first, last),
    )
    for row in requirements:
        item = row["xml_data_item"] or ""
        if item.endswith("REQ_MAX_MW"):
            suffix = "req_max"
        elif item.endswith("REQ_MIN_MW"):
            suffix = "req_min"
        else:
            continue
        column = f"as_sp26_{row['anc_type'].lower()}_{suffix}"
        found.setdefault((row["opr_dt"], row["opr_hr"]), []).append(
            (row["anc_type"], column, row["value"])
        )
    return found


def _index_max(conn, sql: str, params: tuple) -> dict:
    return {
        (row["opr_dt"], row["opr_hr"]): row["value"]
        for row in conn.execute(sql, params)
    }


def _index_direction_max(conn, first: str, last: str) -> dict:
    rows = conn.execute(
        """
        SELECT opr_dt, opr_hr, ti_direction, MAX(value) AS value
        FROM intertie_shadow
        WHERE sp15_related = 1 AND opr_dt >= ? AND opr_dt <= ?
        GROUP BY opr_dt, opr_hr, ti_direction
        """,
        (first, last),
    )
    return {
        ((row["opr_dt"], row["opr_hr"]), row["ti_direction"]): row["value"]
        for row in rows
    }


def _index_flows(conn, first: str, last: str, ties: list[str]) -> dict:
    marks = ",".join("?" for _ in ties)
    found: dict[tuple, dict] = {}
    atc_rows = conn.execute(
        f"""
        SELECT opr_dt, opr_hr, ti_id, ti_direction, value
        FROM tie_atc
        WHERE opr_dt >= ? AND opr_dt <= ? AND ti_id IN ({marks})
        """,
        (first, last, *ties),
    )
    for row in atc_rows:
        slot = found.setdefault(((row["opr_dt"], row["opr_hr"]), row["ti_id"]), {})
        slot[f"atc_{row['ti_direction'].lower()}"] = row["value"]
    flow_rows = conn.execute(
        f"""
        SELECT opr_dt, opr_hr, ti_id, ti_direction, ene_import_mw
        FROM tie_usage
        WHERE opr_dt >= ? AND opr_dt <= ? AND ti_id IN ({marks})
        """,
        (first, last, *ties),
    )
    for row in flow_rows:
        slot = found.setdefault(((row["opr_dt"], row["opr_hr"]), row["ti_id"]), {})
        slot[f"ene_{row['ti_direction'].lower()}"] = row["ene_import_mw"]
    return found


def _query_ties(table, start, end, ti_id, direction, limit, offset, columns, unit) -> dict:
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    where = "opr_dt >= ? AND opr_dt <= ?"
    params: list = [start_day, end_day]
    selected = _ties(ti_id) if ti_id else tie_ids()
    where += f" AND ti_id IN ({','.join('?' for _ in selected)})"
    params.extend(selected)
    direction = direction.upper()
    if direction != "ALL":
        if direction not in {"I", "E"}:
            raise ValueError("direction 要用 I、E 或 ALL")
        where += " AND ti_direction = ?"
        params.append(direction)
    conn = connect()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT issued_on, opr_dt, opr_hr, interval_start AS interval_start_utc,
                   ti_id, ti_direction, {columns}
            FROM {table}
            WHERE {where}
            ORDER BY opr_dt, opr_hr, ti_id, ti_direction
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        return _page(rows, total=total, limit=limit, offset=offset, capped=capped, unit=unit)
    finally:
        conn.close()


def _lmp_types(conn) -> list[str]:
    found = [row[0] for row in conn.execute("SELECT DISTINCT lmp_type FROM dam_lmp ORDER BY 1")]
    types = [item for item in found if item and _SAFE_TYPE.fullmatch(item)]
    if not types:
        return list(_HUB_TYPES)
    ordered = [item for item in _HUB_TYPES if item in types]
    ordered.extend(item for item in types if item not in ordered)
    return ordered


def _node_where(nodes: list[str], start: str, end: str) -> tuple[str, list]:
    marks = ",".join("?" for _ in nodes)
    return (
        f"node IN ({marks}) AND opr_dt >= ? AND opr_dt <= ?",
        [*nodes, start, end],
    )


def _nodes(value: str) -> list[str]:
    if value.upper() == "ALL":
        return node_ids()
    chosen = [part.strip() for part in value.split(",") if part.strip()]
    if not chosen:
        raise ValueError("node 不能为空")
    for node in chosen:
        if not _SAFE_ID.fullmatch(node):
            raise ValueError(f"节点名不合法：{node}")
    return chosen


def _ties(value: str) -> list[str]:
    if not value or value.upper() == "MAJOR":
        return list(MAJOR_TIES)
    if value.upper() == "ALL":
        return tie_ids()
    chosen = [part.strip() for part in value.split(",") if part.strip()]
    if not chosen:
        raise ValueError("ties 不能为空。用 MAJOR、ALL，或逗号分隔的 ti_id。")
    known = set(tie_ids())
    missing = [item for item in chosen if item not in known]
    if missing:
        raise ValueError(f"未知联络线 {missing}。可用 list_catalog 查看 ti_id。")
    return chosen


def _days(start: str, end: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
        raise ValueError("start 和 end 要用 YYYY-MM-DD，都包含当天，时区是 America/Los_Angeles。")
    if end < start:
        raise ValueError("end 早于 start")
    return start, end


def _limit(limit: int, cap: int = 2000) -> tuple[int, bool]:
    if limit < 1:
        raise ValueError("limit 至少为 1")
    if limit > cap:
        return cap, True
    return limit, False


def _offset(offset: int) -> None:
    if offset < 0:
        raise ValueError("offset 不能为负")


def _like(text: str) -> str:
    escaped = text.upper().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _guard_sql(sql: str) -> str:
    statement = sql.strip().rstrip(";").strip()
    if not statement:
        raise ValueError("SQL 是空的")
    if ";" in statement:
        raise ValueError("只允许一条 SELECT")
    if not re.match(r"(?is)^(select|with)\b", statement.lstrip("(")):
        raise ValueError("只允许 SELECT")
    if re.search(
        r"(?is)\b(insert|update|delete|drop|alter|attach|detach|pragma|vacuum|replace|create|grant)\b",
        statement,
    ):
        raise ValueError("只允许只读 SELECT")
    return statement


def query_report(
    report: str,
    start: str,
    end: str,
    forecast_date: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Rows from the long-tail disclosure table.

    ``forecast_date`` filters 预测日期. Leave it empty to return every vintage
    whose operating day falls in the range.
    """
    if not _SAFE_LABEL.fullmatch(report):
        raise ValueError(f"不能识别的报表 {report}")
    start_day, end_day = _days(start, end)
    limit, capped = _limit(limit)
    _offset(offset)
    where = "report = ? AND opr_dt >= ? AND opr_dt <= ?"
    params: list = [report, start_day, end_day]
    if forecast_date:
        if not _SAFE_LABEL.fullmatch(forecast_date):
            raise ValueError("预测日期要用 YYYY-MM-DD")
        where += " AND issued_on = ?"
        params.append(forecast_date)
    conn = connect()
    try:
        _require_table(conn, "disclosure")
        total = conn.execute(f"SELECT COUNT(*) FROM disclosure WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT report, issued_on, opr_dt, opr_hr,
                   interval_start AS interval_start_utc,
                   interval_end AS interval_end_utc,
                   market_run_id, value, attributes
            FROM disclosure
            WHERE {where}
            ORDER BY opr_dt, opr_hr, interval_start
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        parsed = []
        for row in rows:
            item = dict(row)
            try:
                item["attributes"] = json.loads(item["attributes"])
            except (TypeError, json.JSONDecodeError):
                pass
            parsed.append(item)
        return _page(
            parsed,
            total=total,
            limit=limit,
            offset=offset,
            capped=capped,
            unit="见 attributes 里的单位",
            issued_on_means="预测日期。实测等于标的运行日。DAM 是标的日前一天，2DA 前两天，7DA 前七天。",
        )
    finally:
        conn.close()


def _meta(**extra) -> dict:
    meta = {
        "source": "CAISO OASIS https://oasis.caiso.com/oasisapi/SingleZip",
        "timezone": "America/Los_Angeles",
    }
    meta.update(extra)
    return meta


def _page(rows, *, total, limit, offset, capped, **extra) -> dict:
    if rows and not isinstance(rows[0], dict):
        rows = [dict(row) for row in rows]
    return {
        "meta": _meta(
            rows_total=total,
            returned=len(rows),
            limit=limit,
            offset=offset,
            limit_capped=capped,
            **extra,
        ),
        "rows": rows,
    }
