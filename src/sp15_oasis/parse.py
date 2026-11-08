"""Turn OASIS CSV rows into the tables we store."""

from __future__ import annotations

import json

from .catalog import USAGE_COLUMN, classify_nomogram, tie_is_sp15


def num(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _cell(row: dict, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def normalize_lmp(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "node": _cell(row, "NODE", "NODE_ID"),
                "lmp_type": _cell(row, "LMP_TYPE"),
                "xml_data_item": _cell(row, "XML_DATA_ITEM"),
                "value": num(row.get("MW")),
            }
        )
    return [row for row in out if row["interval_start"] and row["node"] and row["lmp_type"]]


def normalize_as_price(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "anc_type": _cell(row, "ANC_TYPE"),
                "anc_region": _cell(row, "ANC_REGION"),
                "xml_data_item": _cell(row, "XML_DATA_ITEM"),
                "value": num(row.get("MW")),
            }
        )
    return [row for row in out if row["interval_start"] and row["anc_type"]]


def normalize_as_requirement(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "anc_type": _cell(row, "ANC_TYPE"),
                "anc_region": _cell(row, "ANC_REGION"),
                "xml_data_item": _cell(row, "XML_DATA_ITEM"),
                "label": _cell(row, "LABEL"),
                "value": num(row.get("MW")),
            }
        )
    return [row for row in out if row["interval_start"] and row["anc_type"] and row["xml_data_item"]]


def normalize_atc(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = _cell(row, "XML_DATA_ITEM")
        if item and item != "ATC_MW":
            continue
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "ti_id": _cell(row, "TI_ID"),
                "ti_direction": _cell(row, "TI_DIRECTION"),
                "value": num(row.get("MW")),
            }
        )
    return [row for row in out if row["interval_start"] and row["ti_id"] and row["ti_direction"]]


def normalize_usage(rows: list[dict]) -> list[dict]:
    """Pivot the long TRNS_USAGE file to one row per hour, tie, and direction."""
    grouped: dict[tuple, dict] = {}
    extras: dict[tuple, dict] = {}
    for row in rows:
        key = (
            _cell(row, "INTERVALSTARTTIME_GMT"),
            _cell(row, "TI_ID"),
            _cell(row, "TI_DIRECTION"),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        current = grouped.get(key)
        if current is None:
            current = {
                "interval_start": key[0],
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "ti_id": key[1],
                "ti_direction": key[2],
            }
            for column in USAGE_COLUMN.values():
                current[column] = None
            grouped[key] = current
        item = _cell(row, "XML_DATA_ITEM")
        column = USAGE_COLUMN.get(item)
        value = num(row.get("MW"))
        if column is None:
            extras.setdefault(key, {})[item or "UNKNOWN"] = {
                "tr_type": _cell(row, "TR_TYPE"),
                "label": _cell(row, "LABEL"),
                "value": value,
            }
        else:
            current[column] = value
    out = []
    for key, row in grouped.items():
        extra = extras.get(key)
        row["extra_json"] = json.dumps(extra, ensure_ascii=False, sort_keys=True) if extra else None
        out.append(row)
    return out


def normalize_intertie_shadow(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        ti_id = _cell(row, "TI_ID")
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "ti_id": ti_id,
                "ti_direction": _cell(row, "TI_DIRECTION"),
                "constraint_cause": _cell(row, "CONSTRAINT_CAUSE"),
                "value": num(row.get("MW")),
                "sp15_related": 1 if tie_is_sp15(ti_id) else 0,
            }
        )
    return [row for row in out if row["interval_start"] and row["ti_id"]]


def normalize_nomogram(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        name = _cell(row, "NOMOGRAM_ID")
        out.append(
            {
                "interval_start": _cell(row, "INTERVALSTARTTIME_GMT"),
                "interval_end": _cell(row, "INTERVALENDTIME_GMT"),
                "opr_dt": _cell(row, "OPR_DT"),
                "opr_hr": int(_cell(row, "OPR_HR") or 0),
                "nomogram_id": name,
                "constraint_cause": _cell(row, "CONSTRAINT_CAUSE"),
                "value": num(row.get("PRC")),
                "region_tag": classify_nomogram(name),
            }
        )
    return [row for row in out if row["interval_start"] and row["nomogram_id"]]
