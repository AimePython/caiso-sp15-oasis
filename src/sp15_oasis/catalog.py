"""What "SP15" means in this database, and which OASIS series we keep.

CAISO publishes a trading hub called TH_SP15_GEN-APND. The name is historical:
SP15 is south of Path 15. In the current market the line that separates the
southern zone from ZP26 is Path 26 (Midway–Vincent 500 kV). Ancillary services
for that southern zone are cleared in region AS_SP26, not in a region named SP15.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

OASIS_API = "https://oasis.caiso.com/oasisapi/SingleZip"
OASIS_PORTAL = (
    "https://www.caiso.com/systems-applications/portals-applications/"
    "open-access-same-time-information-system-oasis"
)
OASIS_FAQ = "https://www.caiso.com/documents/oasis-frequently-asked-questions.pdf"
OASIS_BULK = "https://oasis-bulk.caiso.com/"

HUB = "TH_SP15_GEN-APND"


@dataclass(frozen=True)
class Node:
    node_id: str
    prefix: str
    why: str


@dataclass(frozen=True)
class Tie:
    ti_id: str
    name: str
    group: str
    why: str


NODES: tuple[Node, ...] = (
    Node(HUB, "sp15", "SP15 发电交易枢纽。说“SP15 日前电价”时指的就是这一条。"),
    Node("DLAP_SCE-APND", "sce", "SCE 默认负荷聚合点，SP15 里电量最大的一块。"),
    Node("DLAP_SDGE-APND", "sdge", "SDG&E 默认负荷聚合点，SP15 南部。"),
    Node("DLAP_VEA-APND", "vea", "Valley Electric 默认负荷聚合点，南内华达，电气上靠近 SP15。"),
)

# Transmission interfaces that terminate in, or deliver into, the southern
# California footprint. Northern paths (Malin, NOB, COI, Tracy, Summit) are
# left out on purpose.
TIES: tuple[Tie, ...] = (
    Tie("PALOVRDE_ITC", "Palo Verde", "east_of_river", "亚利桑那 Palo Verde 500kV，SP15 最大的外来电入口。"),
    Tie("DELANEY500_ISL", "Delaney 500", "east_of_river", "Delaney，Palo Verde 一带的南部外来电通道。"),
    Tie("HA500_ISL", "Hassayampa 500", "east_of_river", "Hassayampa 500kV，Palo Verde 枢纽。"),
    Tie("PINALCENT500_ITC", "Pinal Central 500", "east_of_river", "Pinal Central，亚利桑那向南加州送电。"),
    Tie("SUNZIA_ITC", "SunZia", "east_of_river", "SunZia 落在亚利桑那，接入南部通道。"),
    Tie("NORTHGILA500_ITC", "North Gila 500", "east_of_river", "North Gila，Yuma / SDG&E 南部边界。"),
    Tie("BLYTHE_ITC", "Blythe", "east_of_river", "Blythe，SCE 东边界。"),
    Tie("PARKER_ITC", "Parker", "east_of_river", "Parker，科罗拉多河，SCE 东部。"),
    Tie("ELDORADO_ITC", "Eldorado", "eldorado_mead", "Eldorado，南加州和内华达之间的主联络线。"),
    Tie("MEAD_ITC", "Mead", "eldorado_mead", "Mead，南部外来电。"),
    Tie("MEADMKTPC_ITC", "Mead–Marketplace", "eldorado_mead", "Mead 到 Marketplace。"),
    Tie("MEADTMEAD_ITC", "Mead 断面", "eldorado_mead", "Mead 相关调度断面。"),
    Tie("WSTWGMEAD_ITC", "Westwing–Mead", "eldorado_mead", "Westwing 到 Mead。"),
    Tie("MCCULLGH_ITC", "McCullough", "eldorado_mead", "McCullough，Eldorado 一带。"),
    Tie("MCCLMKTPC_ITC", "McCullough–Marketplace", "eldorado_mead", "McCullough 到 Marketplace。"),
    Tie("LAUGHLIN_ITC", "Laughlin", "eldorado_mead", "Laughlin，南内华达 / 科罗拉多河。"),
    Tie("MKTPCADLN_ITC", "Marketplace–Adelanto", "eldorado_mead", "Marketplace 到 Adelanto，进入 SP15。"),
    Tie("IPPDCADLN_ITC", "IPP DC–Adelanto", "adelanto_ipp", "Intermountain 直流落在 Adelanto，SP15 的主要直流入口。"),
    Tie("ADLANTO-SP_ITC", "Adelanto–SP", "adelanto_ipp", "Adelanto 进入 SP15。"),
    Tie("ADLANTOVICTVL-SP_ITC", "Adelanto–Victorville–SP", "adelanto_ipp", "Adelanto / Victorville 进入 SP15。"),
    Tie("VICTVL_ITC", "Victorville", "adelanto_ipp", "Victorville，SCE 系统北部。"),
    Tie("SYLMAR-AC_ITC", "Sylmar AC", "la_basin", "Sylmar 交流，洛杉矶盆地和 LADWP 的边界。"),
    Tie("IID-SCE_ITC", "IID–SCE", "southern_internal", "帝国灌区和 SCE 的边界。"),
    Tie("IID-SDGE_ITC", "IID–SDG&E", "southern_internal", "帝国灌区和 SDG&E 的边界。"),
    Tie("VEA_ITC", "Valley Electric", "southern_nevada", "Valley Electric，南内华达。"),
    Tie("SILVERPK_ITC", "Silver Peak", "eastern_sierra", "Silver Peak，东部联络线。"),
    Tie("CFE_ITC", "CFE", "mexico", "和墨西哥 CFE 的南部边界。"),
    Tie("CFEROA_ITC", "CFE ROA", "mexico", "CFE 南部断面。"),
    Tie("CFETIJ_ITC", "CFE Tijuana", "mexico", "蒂华纳方向的 CFE 联络线。"),
)

# Interfaces that show up as columns on the default training panel.
MAJOR_TIES: tuple[str, ...] = (
    "PALOVRDE_ITC",
    "ELDORADO_ITC",
    "MEAD_ITC",
    "IPPDCADLN_ITC",
    "NORTHGILA500_ITC",
    "BLYTHE_ITC",
    "SYLMAR-AC_ITC",
    "CFE_ITC",
)

# OASIS XML_DATA_ITEM -> column. TR_TYPE and the on-screen label are recorded
# so the wide table can be traced back to TRNS_USAGE. OTC_MW is labeled
# "Hourly TTC" on OASIS; TTC_MW is labeled "Seasonal TTC". USEAGE is their spelling.
USAGE_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("ATC_MW", "atc_mw", "RATING_ATC", "ATC"),
    ("AS_IMPORT_MW", "as_import_mw", "TRNS_AS_IMPORT_IFM", "AS from Imports"),
    ("ENE_IMPORT_MW", "ene_import_mw", "TRNS_ENE_IMPORT_IFM", "Scheduled Net Energy from Imports/Exports"),
    ("CBM_MW", "cbm_mw", "TRNS_RATING_CBM", "CBM"),
    ("CONSTRAINT_MW", "constraint_mw", "TRNS_RATING_CONSTRAINT", "Constraint"),
    ("MKT_XFER_CAP_MW", "mkt_xfer_cap_mw", "TRNS_RATING_MTC", "Market Transfer Capability"),
    ("OTC_MW", "otc_mw", "TRNS_RATING_OTC", "Hourly TTC"),
    ("TRM_MW", "trm_mw", "TRNS_RATING_TRM", "Total TRM"),
    ("TRM_FTO_MW", "trm_fto_mw", "TRNS_RATING_TRM_FTO", "Forced Topology Outages"),
    ("TRM_SPI_MW", "trm_spi_mw", "TRNS_RATING_TRM_SPI", "Simultaneous Path Interaction"),
    ("TRM_UF_MW", "trm_uf_mw", "TRNS_RATING_TRM_UF", "Unscheduled Flow"),
    ("TTC_MW", "ttc_mw", "TRNS_RATING_TTC", "Seasonal TTC"),
    ("USEAGE_MW", "useage_mw", "TRNS_TR_USEAGE", "Hourly Unscheduled TR Capacity"),
)

USAGE_COLUMN = {item: column for item, column, _tr, _label in USAGE_FIELDS}

# Substation and corridor tokens that sit in SCE, SDG&E, Imperial, or on the
# southern interties. This is a label, not a network model: the raw constraint
# name is always stored, and region_tag can be ignored.
_SP15_PATTERNS = (
    r"AVOCDO", r"FALBRK", r"FALLBROOK", r"EL CAJON", r"LOSCOCH", r"SANTEE",
    r"MIRAMAR", r"SCRIPPS", r"COLRIVER", r"COLORIVER", r"INYOKN",
    r"DEV_RDB", r"DEVERS", r"TL23040", r"TL649", r"SYLMAR",
    r"PALOVRDE", r"PALO VERDE", r"ELDORADO", r"\bMEAD\b", r"ADELANT", r"ADLANTO",
    r"VICTVL", r"VICTORV", r"BLYTHE", r"IMPERIAL", r"MIGUEL", r"OTAY",
    r"PENASQUIT", r"SYCAMORE", r"SUNCREST", r"TALEGA", r"OCOTILLO",
    r"LUGO", r"SERRANO", r"MIRA\s*LOMA", r"MIRALOMA", r"WHIRLWIND", r"WINDHUB",
    r"ANTELOPE", r"PARDEE", r"ALBERHILL", r"SONGS", r"SAN ONOFRE",
    r"NORTH\s*GILA", r"\bGILA\b", r"DELANEY", r"HASSAYAMPA", r"PINAL",
    r"SUNZIA", r"SILVERPK", r"MARKETPLACE", r"MCCULL", r"LAUGHLIN",
    r"PATH\s*26", r"PATH26", r"RED\s*BLUFF", r"REDBLUFF", r"ETIWANDA",
    r"RIO\s*HONDO", r"RIOHONDO", r"LAGUNA\s*BELL", r"LAGUBELL",
)
_PATH15_PATTERNS = (r"PATH\s*15", r"PATH15", r"LOS\s*BANOS", r"LOSBANOS")
_SP15_RE = tuple(re.compile(p, re.I) for p in _SP15_PATTERNS)
_PATH15_RE = tuple(re.compile(p, re.I) for p in _PATH15_PATTERNS)

_SP15_TIE_TOKENS = (
    "PALOVRDE", "ELDORADO", "MEAD", "ADLANTO", "VICTVL", "SYLMAR", "CFE",
    "BLYTHE", "PARKER", "IPPDC", "NORTHGILA", "VEA", "IID", "SILVERPK",
    "DELANEY", "SUNZIA", "PINAL", "LAUGHLIN", "MCCULL", "MKTPC", "GILA",
    "HASS", "HA500",
)


def node_ids() -> list[str]:
    return [node.node_id for node in NODES]


def tie_ids() -> list[str]:
    return [tie.ti_id for tie in TIES]


def tie_prefix(ti_id: str) -> str:
    text = ti_id.lower()
    for suffix in ("_itc", "_isl"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text.replace("-", "_")


def classify_nomogram(name: str) -> str:
    """Return sp15, path15, or other.

    Path 26 (Midway–Vincent) is the operating boundary of the SP15 zone, so it
    is tagged sp15. Path 15 (Gates–Midway and the nearby 230 kV lines) is the
    line the hub is named after; it is tagged path15, not dropped.
    """
    text = name.upper()
    if "VINCENT" in text:
        return "sp15"
    if (
        "GATES" in text
        or "PANOCHE" in text
        or "KETTLEMN" in text
        or "HENRIT" in text
        or any(p.search(text) for p in _PATH15_RE)
    ):
        return "path15"
    if any(p.search(text) for p in _SP15_RE):
        return "sp15"
    if "MIDWAY" in text and "VINCENT" in text:
        return "sp15"
    return "other"


def tie_is_sp15(ti_id: str) -> bool:
    if ti_id in {tie.ti_id for tie in TIES}:
        return True
    text = ti_id.upper()
    return any(token in text for token in _SP15_TIE_TOKENS)


def catalog_payload() -> dict:
    return {
        "portal": OASIS_PORTAL,
        "api": OASIS_API,
        "faq": OASIS_FAQ,
        "older_than_39_months": OASIS_BULK,
        "timezone": "America/Los_Angeles",
        "hub": HUB,
        "as_region": "AS_SP26",
        "as_region_why": "CAISO 现在的南部辅助服务区叫 AS_SP26（Path 26 以南），没有名叫 SP15 的 AS 区。SP15 枢纽在这个区里。",
        "retention": "OASIS 在线接口大约只保留 39 个月。本库默认同步 2023-08-01 至今。2016 年起的更早电价在 Historical OASIS Data Downloader，需要自己的 AWS 账号，下载方付流量费。",
        "shadow_null": "联络线约束和支路影子价格只在绑定的小时披露。空值表示该小时没有披露这条约束，不是 0 美元。",
        "direction": "I 是进口到 CAISO，E 是从 CAISO 出口。",
        "price_unit": "USD/MWh。OASIS 的 CSV 把电价列也叫 MW，入库时改成了 value。",
        "capacity_unit": "MW",
        "nodes": [node.__dict__ for node in NODES],
        "ties": [tie.__dict__ for tie in TIES],
        "major_ties": list(MAJOR_TIES),
        "usage_fields": [
            {
                "column": column,
                "xml_data_item": item,
                "tr_type": tr_type,
                "oasis_label": label,
            }
            for item, column, tr_type, label in USAGE_FIELDS
        ],
        "datasets": [
            {
                "name": "dam_lmp",
                "report": "PRC_LMP v12",
                "market": "DAM",
                "what": "日前电价及能量、阻塞、网损、温室气体分量",
                "unit": "USD/MWh",
            },
            {
                "name": "as_price",
                "report": "PRC_AS v12",
                "market": "DAM",
                "what": "AS_SP26 日前辅助服务出清价",
                "unit": "USD/MW",
            },
            {
                "name": "as_requirement",
                "report": "AS_REQ v1",
                "market": "DAM",
                "what": "AS_SP26 日前辅助服务需求",
                "unit": "MW",
            },
            {
                "name": "tie_atc",
                "report": "TRNS_ATC v1",
                "market": "DAM",
                "what": "南部联络线日前可用输电容量",
                "unit": "MW",
            },
            {
                "name": "tie_usage",
                "report": "TRNS_USAGE v1",
                "market": "DAM",
                "what": "南部联络线日前 TTC、OTC、ATC、约束、计划潮流和 TRM",
                "unit": "MW",
            },
            {
                "name": "intertie_shadow",
                "report": "PRC_CNSTR v1",
                "market": "DAM",
                "what": "日前联络线约束影子价格。南部联络线标了 sp15_related，其余披露也留着。",
                "unit": "USD/MWh",
            },
            {
                "name": "nomogram_shadow",
                "report": "PRC_NOMOGRAM v1",
                "market": "DAM",
                "what": "日前支路和诺模图影子价格。region_tag 为 sp15、path15 或 other。",
                "unit": "USD/MWh",
            },
            {
                "name": "load_forecast_dam",
                "report": "SLD_FCST v1",
                "market": "DAM",
                "what": "日前负荷预测，按 TAC 区，含 CA ISO-TAC、SCE-TAC、SDGE-TAC",
                "unit": "MW",
            },
            {
                "name": "load_forecast_2da",
                "report": "SLD_FCST v1",
                "market": "2DA",
                "what": "提前两天的负荷预测",
                "unit": "MW",
            },
            {
                "name": "load_forecast_7da",
                "report": "SLD_FCST v1",
                "market": "7DA",
                "what": "提前七天的负荷预测",
                "unit": "MW",
            },
            {
                "name": "load_actual",
                "report": "SLD_FCST v1",
                "market": "ACTUAL",
                "what": "实际小时负荷",
                "unit": "MW",
            },
            {
                "name": "load_peak",
                "report": "SLD_FCST_PEAK v1",
                "market": "DAM",
                "what": "各 TAC 区的日峰负荷预测",
                "unit": "MW",
            },
            {
                "name": "renewable_forecast",
                "report": "SLD_REN_FCST v1",
                "market": "DAM",
                "what": "日前风电和光伏预测。SP15 是南部枢纽，接口也会带回 NP15、ZP26",
                "unit": "MW",
            },
            {
                "name": "renewable_actual",
                "report": "SLD_REN_FCST v1",
                "market": "ACTUAL",
                "what": "风电和光伏实际出力",
                "unit": "MW",
            },
            {
                "name": "wind_solar_summary",
                "report": "ENE_WIND_SOLAR_SUMMARY v5",
                "market": "DAM and RTD",
                "what": "全网风光合计：日前预测、日前计划、日前净虚拟、实时计划",
                "unit": "MW",
            },
            {
                "name": "fuel_price",
                "report": "PRC_FUEL v1",
                "market": "daily index",
                "what": "各燃料区燃气价格",
                "unit": "USD/mmBtu",
            },
            {
                "name": "ghg_allowance",
                "report": "PRC_GHG_ALLOWANCE v1",
                "market": "daily index",
                "what": "加州碳配额价格指数",
                "unit": "USD/tCO2",
            },
            {
                "name": "as_result",
                "report": "AS_RESULTS v1",
                "market": "DAM",
                "what": "AS_SP26 日前辅助服务采购量、自提供量和成本",
                "unit": "MW 或 USD",
            },
            {
                "name": "system_schedule",
                "report": "ENE_SLRS v1",
                "market": "DAM",
                "what": "日前系统负荷、发电、进口、出口。TAC_SOUTH 是南部区",
                "unit": "MW",
            },
            {
                "name": "disclosure",
                "report": "其余 OASIS 报表，用 report 列区分",
                "market": "见 issued_on",
                "what": (
                    "实时和 HASP 负荷、风光、辅助服务、断面，SP15 四个节点的 5 分钟和 15 分钟电价，"
                    "全联络线潮流、EIM、灵活爬坡、CRR、公开报价和名录。"
                    "issued_on 是预测日期，opr_dt 是标的运行日。"
                ),
                "unit": "见 attributes",
            },
        ],
        "not_in_this_archive": (
            "5 分钟和 15 分钟电价只保留 SP15 的 4 个节点，没有全网每个节点。"
            "全机组的期望电量和调度指令没有按节点过滤的接口，没有整库接入。"
            "名录类报表如果必须逐个资源 ID 才能查，也不在这个库里。"
        ),
    }
