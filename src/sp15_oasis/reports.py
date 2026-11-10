"""OASIS reports that land in the generic disclosure table.

Each row keeps opr_dt (the operating day the value is about) and issued_on
(the Pacific date a model could have known it). Actuals use the operating
day itself. DAM is the day before, 2DA two days before, 7DA seven days
before. HASP, RTPD and RTD use the Pacific date of the interval start minus
75, 30 and 5 minutes.

Five-minute and fifteen-minute prices are limited to the four SP15 nodes.
Resource-level settlement for the whole fleet is not requested.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime

from .calendar import PT, UTC, issued_on, trading_bounds

_NODES = "TH_SP15_GEN-APND,DLAP_SCE-APND,DLAP_SDGE-APND,DLAP_VEA-APND"
_VALUE_KEYS = ("MW", "PRC", "VALUE", "LOAD_MW", "GHG_PRC_IDX")


@dataclass(frozen=True)
class Report:
    name: str
    queryname: str
    version: str
    market: str
    extra: tuple[tuple[str, str], ...] = ()
    chunk_days: int = 31
    path: str = "SingleZip"
    sparse: bool = False
    retry_empty: bool = False


def _r(
    name: str,
    queryname: str,
    version: str,
    market: str,
    extra: tuple[tuple[str, str], ...] = (),
    chunk_days: int = 31,
    path: str = "SingleZip",
    sparse: bool = False,
    retry_empty: bool = False,
) -> Report:
    return Report(name, queryname, version, market, extra, chunk_days, path, sparse, retry_empty)


REPORTS: tuple[Report, ...] = (
    _r("load_rtpd", "SLD_FCST", "1", "RTPD", (("market_run_id", "RTM"), ("execution_type", "RTPD")), 1),
    _r("load_rtd", "SLD_FCST", "1", "RTD", (("market_run_id", "RTM"), ("execution_type", "RTD")), 1),
    _r("load_adv_rtpd", "SLD_ADV_FCST", "4", "RTPD", (("market_run_id", "RTPD"),), 1),
    _r("load_adv_rtd", "SLD_ADV_FCST", "4", "RTD", (("market_run_id", "RTD"),), 1),
    _r("load_eval_hourly", "SLD_SF_EVAL_DMD_FCST", "4", "ACTUAL", (("granularity", "HOURLY"),)),
    _r("renewable_hasp", "SLD_REN_FCST", "1", "HASP", (("market_run_id", "HASP"),)),
    _r("renewable_rtpd", "SLD_REN_FCST", "1", "RTPD", (("market_run_id", "RTPD"),), 1),
    _r("renewable_rtd", "SLD_REN_FCST", "1", "RTD", (("market_run_id", "RTD"),), 1),
    _r("as_req_hasp", "AS_REQ", "1", "HASP", (("market_run_id", "HASP"), ("anc_type", "ALL"), ("anc_region", "ALL"))),
    _r("as_req_rtm", "AS_REQ", "1", "RTM", (("market_run_id", "RTM"), ("anc_type", "ALL"), ("anc_region", "ALL"))),
    _r("as_result_hasp", "AS_RESULTS", "1", "HASP", (("market_run_id", "HASP"), ("anc_type", "ALL"), ("anc_region", "ALL"))),
    _r("as_result_rtm", "AS_RESULTS", "1", "RTM", (("market_run_id", "RTM"), ("anc_type", "ALL"), ("anc_region", "ALL"))),
    _r("as_op_rsrv", "AS_OP_RSRV", "1", "RTD"),
    _r("as_mileage", "AS_MILEAGE_CALC", "1", "RTD"),
    _r("slrs_hasp", "ENE_SLRS", "1", "HASP", (("market_run_id", "HASP"), ("tac_zone_name", "ALL"), ("schedule", "ALL"))),
    _r("slrs_ruc", "ENE_SLRS", "1", "RUC", (("market_run_id", "RUC"), ("tac_zone_name", "ALL"), ("schedule", "ALL"))),
    _r("slrs_rtm", "ENE_SLRS", "1", "RTM", (("market_run_id", "RTM"), ("tac_zone_name", "ALL"), ("schedule", "ALL")), 1),
    _r("tie_usage_all_dam", "TRNS_USAGE", "1", "DAM", (("market_run_id", "DAM"), ("ti_id", "ALL"), ("ti_direction", "ALL"))),
    _r("tie_usage_hasp", "TRNS_USAGE", "1", "HASP", (("market_run_id", "HASP"), ("ti_id", "ALL"), ("ti_direction", "ALL"))),
    _r("tie_usage_rtm", "TRNS_USAGE", "1", "RTM", (("market_run_id", "RTM"), ("ti_id", "ALL"), ("ti_direction", "ALL")), 1),
    _r("rtm_flowgate", "PRC_RTM_FLOWGATE", "1", "RTPD", (), 1),
    _r("rtm_nomogram", "PRC_RTM_NOMOGRAM", "1", "RTPD", (), 1),
    _r("lmp_rtm_5min", "PRC_INTVL_LMP", "3", "RTD", (("market_run_id", "RTM"), ("node", _NODES)), 1),
    _r("lmp_rtpd", "PRC_RTPD_LMP", "3", "RTPD", (("market_run_id", "RTPD"), ("node", _NODES)), 1),
    _r("lmp_hasp", "PRC_HASP_LMP", "3", "HASP", (("market_run_id", "HASP"), ("node", _NODES)), 1),
    _r("lmp_sptie_dam", "PRC_SPTIE_LMP", "5", "DAM", (("market_run_id", "DAM"), ("node", _NODES))),
    _r("lmp_sptie_rtpd", "PRC_SPTIE_LMP", "5", "RTPD", (("market_run_id", "RTPD"), ("node", _NODES)), 1),
    _r("lmp_sptie_rtd", "PRC_SPTIE_LMP", "5", "RTD", (("market_run_id", "RTD"), ("node", _NODES)), 1),
    _r("mpm_dam", "ENE_MPM", "1", "DAM", (("market_run_id", "DAM"), ("node", _NODES))),
    _r("mpm_hasp", "ENE_MPM", "1", "HASP", (("market_run_id", "HASP"), ("node", _NODES))),
    _r("loss_dam", "ENE_LOSS", "1", "DAM", (("market_run_id", "DAM"),)),
    _r("rmr", "CMMT_RMR", "1", "DAM", (("market_run_id", "DAM"),)),
    _r("ra_mlc", "CMMT_RA_MLC", "1", "DAM", (("market_run_id", "DAM"),)),
    _r("cb_awards", "ENE_CB_AWARDS", "1", "DAM", (("market_run_id", "DAM"), ("node", _NODES))),
    _r("cb_cleared", "ENE_CB_CLR_AWARDS", "1", "DAM", (("market_run_id", "DAM"),)),
    _r("cb_summary", "ENE_CB_MKT_SUM", "1", "DAM"),
    _r("outage_aggregate", "AGGR_OUTAGE_SCH", "1", "ACTUAL", (("fuel_category", "ALL"), ("trading_hub", "ALL"))),
    _r("transmission_outage", "TRNS_OUTAGE", "1", "ACTUAL", (("ti_id", "ALL"), ("ti_direction", "ALL")), 31, "SingleZip", True),
    _r("eim_transfer_rtpd", "ENE_EIM_TRANSFER", "1", "RTPD", (("market_run_id", "RTPD"), ("baa_grp_id", "ALL")), 1),
    _r("eim_transfer_rtd", "ENE_EIM_TRANSFER", "1", "RTD", (("market_run_id", "RTD"), ("baa_grp_id", "ALL")), 1),
    _r("eim_limits_rtpd", "ENE_EIM_TRANSFER_LIMITS", "1", "RTPD", (("market_run_id", "RTPD"), ("baa_grp_id", "ALL")), 1),
    _r("eim_limits_rtd", "ENE_EIM_TRANSFER_LIMITS", "1", "RTD", (("market_run_id", "RTD"), ("baa_grp_id", "ALL")), 1),
    _r("flex_ramp", "ENE_AGGR_FLEX_RAMP", "1", "RTPD", (("market_run_id", "RTPD"), ("baa_grp_id", "ALL")), 1),
    _r("uncertainty", "ENE_UNCERTAINTY_MV", "1", "RTD", (("market_run_id", "RTD"), ("baa_grp_id", "ALL")), 1),
    _r("crr_clearing", "CRR_CLEARING", "1", "DAM", (("market_name", "ALL"),)),
    _r("crr_inventory", "CRR_INVENTORY", "1", "DAM"),
    _r("public_bids_dam", "PUB_DAM_GRP", "3", "DAM", (), 1, "GroupZip", True, True),
    _r("public_bids_rtm", "PUB_RTM_GRP", "3", "RTD", (), 1, "GroupZip", True, True),
    _r("public_bids_cb", "PUB_CB_DAM_GRP", "3", "DAM", (), 1, "GroupZip", True, True),
    _r("atlas_hub", "ATL_HUB", "1", "ACTUAL", (), 31, "SingleZip", True),
    _r("atlas_tac", "ATL_TAC", "1", "ACTUAL", (), 31, "SingleZip", True),
    _r("atlas_tie", "ATL_TI", "1", "ACTUAL", (("ti_type", "ALL"),), 31, "SingleZip", True),
)


def params_for(report: Report):
    def build(start: date, end: date, values: list[str]) -> dict[str, str]:
        del values
        start_gmt, end_gmt = trading_bounds(start, end)
        params = {
            "version": report.version,
            "startdatetime": start_gmt,
            "enddatetime": end_gmt,
            "resultformat": "6",
            **dict(report.extra),
        }
        if report.path == "GroupZip":
            params["groupid"] = report.queryname
        else:
            params["queryname"] = report.queryname
        return params

    return build


def normalize_report(report: Report):
    def normalize(rows: list[dict]) -> list[dict]:
        kept: list[dict] = []
        for raw in rows:
            identity: dict[str, str] = {}
            value = None
            for key, cell in raw.items():
                name = key.upper()
                if name == "GROUP" or name == "POS" or name.endswith("_POS"):
                    continue
                text = (cell or "").strip()
                if not text:
                    continue
                if name in _VALUE_KEYS and value is None:
                    try:
                        value = float(text)
                        continue
                    except ValueError:
                        pass
                identity[name] = text
            day = _operating_day(identity)
            if day is None:
                continue
            interval = identity.get("INTERVALSTARTTIME_GMT") or identity.get("INTERVALSTARTTIME") or ""
            key_text = json.dumps(identity, sort_keys=True, ensure_ascii=False)
            kept.append(
                {
                    "report": report.name,
                    "issued_on": issued_on(day, report.market, interval or None).isoformat(),
                    "opr_dt": day.isoformat(),
                    "opr_hr": int(identity.get("OPR_HR") or 0),
                    "interval_start": interval or day.isoformat(),
                    "interval_end": identity.get("INTERVALENDTIME_GMT") or "",
                    "market_run_id": report.market,
                    "row_key": hashlib.sha1(key_text.encode()).hexdigest(),
                    "attributes": key_text,
                    "value": value,
                }
            )
        return kept

    return normalize


def _operating_day(identity: dict[str, str]) -> date | None:
    opr = identity.get("OPR_DT")
    if opr:
        try:
            return date.fromisoformat(opr[:10])
        except ValueError:
            return None
    interval = identity.get("INTERVALSTARTTIME_GMT") or identity.get("INTERVALSTARTTIME")
    if not interval:
        return None
    text = interval.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(PT).date()
