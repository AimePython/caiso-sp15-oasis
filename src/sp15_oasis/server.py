"""MCP server. Speak JSON-RPC on stdin/stdout; logs stay on stderr."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .db import MissingDatabase
from . import query as q

mcp = MCPServer(
    "caiso-sp15",
    log_level="WARNING",
    instructions=(
        "本地 CAISO OASIS 数据库，只含公开披露。"
        "SP15 日前电价是节点 TH_SP15_GEN-APND，单位美元/MWh，另外有 SCE、SDG&E、VEA 三个南部负荷聚合点。"
        "南部辅助服务区在 OASIS 里叫 AS_SP26，不是 SP15。"
        "每条数据都有 opr_dt（标的运行日）和 issued_on（预测日期）。"
        "标的日 10 月 10 日：DAM 是 10 月 9 日预测的，2DA 是 10 月 8 日，7DA 是 10 月 3 日；实测的预测日期等于标的日。"
        "另外有小时负荷预测和实际负荷、风光预测和实际出力、燃料价格、碳配额、AS_SP26 日前结果、南部系统发用电计划。"
        "其余报表在 disclosure 表，用 query_report 按 report 名查询。5 分钟和 15 分钟电价只保留 SP15 四个节点。"
        "边界数据是南部联络线的日前 ATC 和断面使用，以及日前联络线约束、支路/诺模图影子价格。"
        "影子价格为空表示该小时没有披露这条约束为绑定，不是 0。"
        "运行日是 America/Los_Angeles。日期参数都包含当天。"
        "在线 OASIS 大约只保留 39 个月。先看 dataset_coverage，再查 training_panel 或单张表。"
    ),
)


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (MissingDatabase, ValueError) as exc:
        return {"error": str(exc)}


@mcp.tool(name="list_catalog", structured_output=False)
def list_catalog() -> dict:
    """列出数据范围：节点、南部联络线、报表、单位，以及库里已经有多少天。

    先调用这个工具，再决定查询哪张表。
    """
    return _safe(q.list_catalog)


@mcp.tool(name="dataset_coverage", structured_output=False)
def dataset_coverage() -> dict:
    """每张表的行数、最早和最晚运行日，以及同步块是否完成。"""
    return _safe(q.dataset_coverage)


@mcp.tool(name="query_dam_prices", structured_output=False)
def query_dam_prices_tool(
    start: str,
    end: str,
    node: str = "TH_SP15_GEN-APND",
    component: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询日前电价，单位美元/MWh。

    start、end：运行日 YYYY-MM-DD，含首尾，时区 America/Los_Angeles。
    node：TH_SP15_GEN-APND、DLAP_SCE-APND、DLAP_SDGE-APND、DLAP_VEA-APND，可逗号分隔，或 ALL。
    component：ALL 时每个节点每小时一行，LMP、MCC、MCE、MCL、MGHG 分成列。也可以指定其中一个分量。
    """
    return _safe(q.query_dam_prices, start, end, node, component, limit, offset)


@mcp.tool(name="query_ancillary", structured_output=False)
def query_ancillary_tool(
    start: str,
    end: str,
    kind: str = "price",
    anc_type: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询 AS_SP26（SP15 所在的南部辅助服务区）的日前价格或需求。

    kind：price（美元/MW）、requirement（MW）或 result（日前采购量，MW；uom 为 2 时 value 是美元成本）。
    anc_type：可空。常见值 RU、RD、SR、NR、RMU、RMD。
    """
    return _safe(q.query_ancillary, start, end, kind, anc_type, limit, offset)


@mcp.tool(name="query_tie_atc", structured_output=False)
def query_tie_atc_tool(
    start: str,
    end: str,
    ti_id: str = "",
    direction: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询南部联络线日前可用输电容量，单位 MW。

    ti_id 为空则返回目录里的全部南部联络线，也可以逗号分隔。
    direction：I 进口到 CAISO，E 出口，ALL 两个方向。
    """
    return _safe(q.query_tie_atc, start, end, ti_id, direction, limit, offset)


@mcp.tool(name="query_tie_usage", structured_output=False)
def query_tie_usage_tool(
    start: str,
    end: str,
    ti_id: str = "",
    direction: str = "ALL",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询南部联络线日前断面：TTC、OTC、ATC、约束、计划潮流、TRM，单位 MW。

    OASIS 把 OTC_MW 标成 Hourly TTC，把 TTC_MW 标成 Seasonal TTC。
    useage_mw 沿用 OASIS 的拼写，含义是未安排的输电权容量。
    ene_import_mw 是该方向的计划净交换。
    """
    return _safe(q.query_tie_usage, start, end, ti_id, direction, limit, offset)


@mcp.tool(name="query_shadow_prices", structured_output=False)
def query_shadow_prices_tool(
    start: str,
    end: str,
    kind: str = "nomogram",
    region: str = "related",
    name_contains: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询日前影子价格，单位美元/MWh。只包含被披露为绑定的小时。

    kind：nomogram 是支路和诺模图，intertie 是联络线约束。
    region：related（默认，sp15 加 path15）、sp15、path15、all。
    Path 26（Midway–Vincent）标成 sp15。Path 15（Gates–Midway 一带）标成 path15。
    region_tag 是地名启发式，原始约束名在 nomogram_id 里。
    """
    return _safe(q.query_shadow_prices, start, end, kind, region, name_contains, limit, offset)


@mcp.tool(name="training_panel", structured_output=False)
def training_panel_tool(
    start: str,
    end: str,
    ties: str = "MAJOR",
    limit: int = 168,
    offset: int = 0,
) -> dict:
    """事后同小时关联表，不是防泄漏预测训练集。预测训练请使用 research_training。

    含 SP15 枢纽电价、南部聚合点、AS_SP26、Path 26/15 影子价格、主要联络线 ATC 和计划潮流。
    同目标日的出清量、电价分量及影子价格不得用于预测该日 DAM 价格。

    ties：MAJOR（默认 8 条主干联络线）、ALL，或逗号分隔的 ti_id。
    影子价格列为空表示该小时没有披露绑定，训练时不要未经说明就填成 0。
    一次最多 5000 小时，用 offset 翻页。要整段导出用命令行 export。
    """
    return _safe(q.training_panel, start, end, ties, limit, offset)


@mcp.tool(name="query_load", structured_output=False)
def query_load_tool(
    start: str,
    end: str,
    market: str = "DAM",
    tac_area: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询小时负荷，单位 MW。

    market：DAM 是日前预测，2DA、7DA 是更早的预测，ACTUAL 是实际负荷，PEAK 是各区日峰预测。
    tac_area：可空表示全部。常用 CA ISO-TAC、SCE-TAC、SDGE-TAC、VEA-TAC。
    """
    return _safe(q.query_load, start, end, market, tac_area, limit, offset)


@mcp.tool(name="query_renewables", structured_output=False)
def query_renewables_tool(
    start: str,
    end: str,
    market: str = "ACTUAL",
    trading_hub: str = "SP15",
    renewable_type: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询风电和光伏，单位 MW。

    market：DAM 是日前预测，ACTUAL 是实际出力，SUMMARY 是全网风光合计。
    trading_hub：SP15、NP15、ZP26 或 ALL。SUMMARY 不按枢纽拆。
    renewable_type：Wind、Solar，或空表示两种都要。
    """
    return _safe(q.query_renewables, start, end, market, trading_hub, renewable_type, limit, offset)


@mcp.tool(name="query_report", structured_output=False)
def query_report_tool(
    report: str,
    start: str,
    end: str,
    forecast_date: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询 disclosure 表里的其余报表。

    report 是数据集名，例如 lmp_rtm_5min、load_rtpd、renewable_hasp、public_bids_dam。
    start 和 end 是标的运行日。forecast_date 是预测日期，可空。
    标的日 2026-10-10 的日前数据，预测日期是 2026-10-09；提前两天是 2026-10-08。
    实测的预测日期等于标的运行日。
    """
    return _safe(q.query_report, report, start, end, forecast_date, limit, offset)


@mcp.tool(name="query_fuel", structured_output=False)
def query_fuel_tool(
    start: str,
    end: str,
    fuel_region_id: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询燃料区燃气价格，单位美元/mmBtu。fuel_region_id 可空，表示全部区域。"""
    return _safe(q.query_fuel, start, end, fuel_region_id, limit, offset)


@mcp.tool(name="query_ghg", structured_output=False)
def query_ghg_tool(start: str, end: str, limit: int = 200, offset: int = 0) -> dict:
    """查询加州碳配额价格指数，一天一条，单位美元/吨。"""
    return _safe(q.query_ghg, start, end, limit, offset)


@mcp.tool(name="query_system_schedule", structured_output=False)
def query_system_schedule_tool(
    start: str,
    end: str,
    tac_zone: str = "TAC_SOUTH",
    schedule: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """查询日前系统发用电计划，单位 MW。

    tac_zone：TAC_SOUTH 是南部，Caiso_Totals 是全网，也可以传 ALL。
    schedule：Load、Generation、Import、Export，或空表示全部。
    """
    return _safe(q.query_system_schedule, start, end, tac_zone, schedule, limit, offset)


@mcp.tool(name="query_sql", structured_output=False)
def query_sql_tool(sql: str, limit: int = 200) -> dict:
    """对本地库执行一条只读 SELECT。表名见 dataset_coverage 的 queryable_tables。

    只能有一条语句。写入会被拒绝。默认最多返回 200 行，上限 1000。
    """
    return _safe(q.query_sql, sql, limit)


# Frozen research partitions; daily collector and original archive are unchanged.
from .research import register as _register_research
_register_research(mcp)

# Weather forecasts use a separate versioned archive.
from .weather import register as _register_weather
_register_weather(mcp)
