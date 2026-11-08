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

    kind：price（美元/MW）或 requirement（MW）。
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
    """按运行小时拼好的训练表：SP15 枢纽电价、南部聚合点、AS_SP26、Path 26/15 影子价格、主要联络线 ATC 和计划潮流。

    ties：MAJOR（默认 8 条主干联络线）、ALL，或逗号分隔的 ti_id。
    影子价格列为空表示该小时没有披露绑定，训练时不要未经说明就填成 0。
    一次最多 5000 小时，用 offset 翻页。要整段导出用命令行 export。
    """
    return _safe(q.training_panel, start, end, ties, limit, offset)


@mcp.tool(name="query_sql", structured_output=False)
def query_sql_tool(sql: str, limit: int = 200) -> dict:
    """对本地库执行一条只读 SELECT。表名见 dataset_coverage 的 queryable_tables。

    只能有一条语句。写入会被拒绝。默认最多返回 200 行，上限 1000。
    """
    return _safe(q.query_sql, sql, limit)
