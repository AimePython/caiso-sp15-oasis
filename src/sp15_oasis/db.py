"""SQLite storage for the SP15 extract."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from .calendar import issued_on
from .paths import db_path

TABLES: dict[str, tuple[str, ...]] = {
    "dam_lmp": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "node",
        "lmp_type",
        "xml_data_item",
        "value",
    ),
    "as_price": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "anc_type",
        "anc_region",
        "xml_data_item",
        "value",
    ),
    "as_requirement": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "anc_type",
        "anc_region",
        "xml_data_item",
        "label",
        "value",
    ),
    "tie_atc": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "ti_id",
        "ti_direction",
        "value",
    ),
    "tie_usage": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "ti_id",
        "ti_direction",
        "atc_mw",
        "as_import_mw",
        "ene_import_mw",
        "cbm_mw",
        "constraint_mw",
        "mkt_xfer_cap_mw",
        "otc_mw",
        "trm_mw",
        "trm_fto_mw",
        "trm_spi_mw",
        "trm_uf_mw",
        "ttc_mw",
        "useage_mw",
        "extra_json",
    ),
    "intertie_shadow": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "ti_id",
        "ti_direction",
        "constraint_cause",
        "value",
        "sp15_related",
    ),
    "nomogram_shadow": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "nomogram_id",
        "constraint_cause",
        "value",
        "region_tag",
    ),
    "load": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "market_run_id",
        "tac_area",
        "xml_data_item",
        "label",
        "value",
    ),
    "load_peak": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "tac_area",
        "value",
    ),
    "renewable": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "market_run_id",
        "trading_hub",
        "renewable_type",
        "xml_data_item",
        "value",
    ),
    "wind_solar_summary": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "market_run_id",
        "data_item",
        "value",
    ),
    "fuel_price": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "fuel_region_id",
        "value",
    ),
    "ghg_allowance": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "value",
    ),
    "as_result": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "anc_type",
        "anc_region",
        "result_type",
        "xml_data_item",
        "uom",
        "value",
    ),
    "system_schedule": (
        "interval_start",
        "interval_end",
        "opr_dt",
        "opr_hr",
        "market_run_id",
        "tac_zone",
        "schedule",
        "xml_data_item",
        "value",
    ),
    "disclosure": (
        "report",
        "issued_on",
        "opr_dt",
        "opr_hr",
        "interval_start",
        "interval_end",
        "market_run_id",
        "row_key",
        "attributes",
        "value",
    ),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS dam_lmp (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    node TEXT NOT NULL,
    lmp_type TEXT NOT NULL,
    xml_data_item TEXT,
    value REAL,
    PRIMARY KEY (interval_start, node, lmp_type)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS as_price (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    anc_type TEXT NOT NULL,
    anc_region TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, anc_type, anc_region, xml_data_item)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS as_requirement (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    anc_type TEXT NOT NULL,
    anc_region TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    label TEXT,
    value REAL,
    PRIMARY KEY (interval_start, anc_type, anc_region, xml_data_item)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS tie_atc (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    ti_id TEXT NOT NULL,
    ti_direction TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, ti_id, ti_direction)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS tie_usage (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    ti_id TEXT NOT NULL,
    ti_direction TEXT NOT NULL,
    atc_mw REAL,
    as_import_mw REAL,
    ene_import_mw REAL,
    cbm_mw REAL,
    constraint_mw REAL,
    mkt_xfer_cap_mw REAL,
    otc_mw REAL,
    trm_mw REAL,
    trm_fto_mw REAL,
    trm_spi_mw REAL,
    trm_uf_mw REAL,
    ttc_mw REAL,
    useage_mw REAL,
    extra_json TEXT,
    PRIMARY KEY (interval_start, ti_id, ti_direction)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS intertie_shadow (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    ti_id TEXT NOT NULL,
    ti_direction TEXT NOT NULL,
    constraint_cause TEXT NOT NULL,
    value REAL,
    sp15_related INTEGER NOT NULL,
    PRIMARY KEY (interval_start, ti_id, ti_direction, constraint_cause)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS nomogram_shadow (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    nomogram_id TEXT NOT NULL,
    constraint_cause TEXT NOT NULL,
    value REAL,
    region_tag TEXT NOT NULL,
    PRIMARY KEY (interval_start, nomogram_id, constraint_cause)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS sync_chunk (
    dataset TEXT NOT NULL,
    chunk_start TEXT NOT NULL,
    chunk_end TEXT NOT NULL,
    rows INTEGER,
    status TEXT NOT NULL,
    detail TEXT,
    fetched_at TEXT,
    PRIMARY KEY (dataset, chunk_start, chunk_end)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS ix_lmp_node_dt ON dam_lmp(node, lmp_type, opr_dt, opr_hr);
CREATE INDEX IF NOT EXISTS ix_as_price_dt ON as_price(opr_dt, anc_type);
CREATE INDEX IF NOT EXISTS ix_as_req_dt ON as_requirement(opr_dt, anc_type);
CREATE INDEX IF NOT EXISTS ix_atc_dt ON tie_atc(opr_dt, ti_id, ti_direction);
CREATE INDEX IF NOT EXISTS ix_usage_dt ON tie_usage(opr_dt, ti_id, ti_direction);
CREATE INDEX IF NOT EXISTS ix_nom_dt ON nomogram_shadow(opr_dt, region_tag);
CREATE INDEX IF NOT EXISTS ix_cnstr_dt ON intertie_shadow(opr_dt, sp15_related);

CREATE TABLE IF NOT EXISTS load (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    market_run_id TEXT NOT NULL,
    tac_area TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    label TEXT,
    value REAL,
    PRIMARY KEY (interval_start, market_run_id, tac_area, xml_data_item)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS load_peak (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    tac_area TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, tac_area)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS renewable (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    market_run_id TEXT NOT NULL,
    trading_hub TEXT NOT NULL,
    renewable_type TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, market_run_id, trading_hub, renewable_type)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS wind_solar_summary (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    market_run_id TEXT NOT NULL,
    data_item TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, market_run_id, data_item)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS fuel_price (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    fuel_region_id TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, fuel_region_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ghg_allowance (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (opr_dt)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS as_result (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    anc_type TEXT NOT NULL,
    anc_region TEXT NOT NULL,
    result_type TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    uom TEXT,
    value REAL,
    PRIMARY KEY (interval_start, anc_type, anc_region, xml_data_item)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS system_schedule (
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    opr_dt TEXT NOT NULL,
    opr_hr INTEGER NOT NULL,
    market_run_id TEXT NOT NULL,
    tac_zone TEXT NOT NULL,
    schedule TEXT NOT NULL,
    xml_data_item TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (interval_start, market_run_id, tac_zone, schedule, xml_data_item)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS ix_load_dt ON load(opr_dt, market_run_id, tac_area);
CREATE INDEX IF NOT EXISTS ix_load_peak_dt ON load_peak(opr_dt, tac_area);
CREATE INDEX IF NOT EXISTS ix_ren_dt ON renewable(opr_dt, market_run_id, trading_hub);
CREATE INDEX IF NOT EXISTS ix_fuel_dt ON fuel_price(opr_dt, fuel_region_id);
CREATE INDEX IF NOT EXISTS ix_sched_dt ON system_schedule(opr_dt, tac_zone);

CREATE TABLE IF NOT EXISTS disclosure (
    report TEXT NOT NULL,
    issued_on TEXT NOT NULL,
    opr_dt TEXT,
    opr_hr INTEGER,
    interval_start TEXT NOT NULL,
    interval_end TEXT,
    market_run_id TEXT NOT NULL,
    row_key TEXT NOT NULL,
    attributes TEXT NOT NULL,
    value REAL,
    PRIMARY KEY (report, row_key)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS ix_disclosure_dt ON disclosure(report, opr_dt, issued_on);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT
) WITHOUT ROWID;
"""


class MissingDatabase(FileNotFoundError):
    def __init__(self, path) -> None:
        super().__init__(
            f"还没有本地库 {path}。在仓库里运行：.venv/bin/python -m sp15_oasis sync"
        )


def connect(*, write: bool = False) -> sqlite3.Connection:
    path = db_path()
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=120)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-200000")
        init_schema(conn)
        return conn
    if not path.exists():
        raise MissingDatabase(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_issued_on(conn)


_BACKFILL_SQL = {
    "load": """CASE market_run_id
        WHEN '2DA' THEN date(opr_dt, '-2 day')
        WHEN '7DA' THEN date(opr_dt, '-7 day')
        WHEN 'ACTUAL' THEN opr_dt
        ELSE date(opr_dt, '-1 day') END""",
    "renewable": """CASE market_run_id
        WHEN 'ACTUAL' THEN opr_dt
        ELSE date(opr_dt, '-1 day') END""",
    "wind_solar_summary": """CASE market_run_id
        WHEN 'RTD' THEN opr_dt
        WHEN 'RTM' THEN opr_dt
        WHEN 'HASP' THEN opr_dt
        WHEN 'ACTUAL' THEN opr_dt
        ELSE date(opr_dt, '-1 day') END""",
    "system_schedule": """CASE market_run_id
        WHEN 'HASP' THEN opr_dt
        WHEN 'RTM' THEN opr_dt
        WHEN 'RTD' THEN opr_dt
        WHEN 'ACTUAL' THEN opr_dt
        ELSE date(opr_dt, '-1 day') END""",
}


def ensure_issued_on(conn: sqlite3.Connection) -> None:
    """Add 预测日期 and fill it once for rows stored before the column existed."""
    existing = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    added = False
    for table in TABLES:
        if table not in existing or table == "disclosure":
            continue
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "issued_on" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN issued_on TEXT")
            added = True
    done = conn.execute("SELECT value FROM schema_meta WHERE key = 'issued_on_v1'").fetchone()
    if done and not added:
        return
    for table in TABLES:
        if table == "disclosure" or table not in existing:
            continue
        expr = _BACKFILL_SQL.get(table, "date(opr_dt, '-1 day')")
        conn.execute(
            f"UPDATE {table} SET issued_on = {expr} "
            "WHERE issued_on IS NULL AND opr_dt IS NOT NULL"
        )
        conn.commit()
    conn.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('issued_on_v1', '1')")
    conn.commit()


def _with_issued(table: str, row: dict) -> dict:
    del table
    if row.get("issued_on") or not row.get("opr_dt"):
        return row
    market = str(row.get("market_run_id") or "DAM")
    day = date.fromisoformat(str(row["opr_dt"])[:10])
    stamped = dict(row)
    stamped["issued_on"] = issued_on(day, market, row.get("interval_start")).isoformat()
    return stamped


def upsert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> int:
    columns = TABLES[table]
    if not rows:
        return 0
    if "issued_on" not in columns:
        columns = (*columns, "issued_on")
    prepared = [_with_issued(table, row) for row in rows]
    placeholders = ",".join("?" for _ in columns)
    sql = (
        f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    payload = [tuple(row.get(column) for column in columns) for row in prepared]
    conn.executemany(sql, payload)
    return len(payload)


def mark_chunk(
    conn: sqlite3.Connection,
    dataset: str,
    chunk_start: str,
    chunk_end: str,
    status: str,
    rows: int,
    detail: str = "",
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sync_chunk
            (dataset, chunk_start, chunk_end, rows, status, detail, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset,
            chunk_start,
            chunk_end,
            rows,
            status,
            detail[:500],
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )


def chunk_status(conn: sqlite3.Connection, dataset: str, chunk_start: str, chunk_end: str) -> str | None:
    row = conn.execute(
        """
        SELECT status FROM sync_chunk
        WHERE dataset = ? AND chunk_start = ? AND chunk_end = ?
        """,
        (dataset, chunk_start, chunk_end),
    ).fetchone()
    return None if row is None else row["status"]
