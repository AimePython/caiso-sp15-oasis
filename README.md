# CAISO SP15 OASIS MCP

把 [CAISO OASIS](https://www.caiso.com/systems-applications/portals-applications/open-access-same-time-information-system-oasis) 上和 SP15 有关的日前电价、南部边界、影子价格、负荷、风光、燃料、碳价和系统计划下到本地 SQLite，再用 MCP 查询。其余实时/HASP 报表进 `disclosure`。气象是另一份 Open-Meteo 库。给同组的人训练模型用。数据是公开披露，这个仓库只提供下载和查询。

在线接口大约只保留 **39 个月**。默认从 `2023-08-01` 同步到太平洋时区的今天。2016 年以后、超出 39 个月的电价在 [Historical OASIS Data Downloader](https://oasis-bulk.caiso.com/)，要自己的 AWS 账号，下载流量由下载方付。本工具不会去连那个桶。

## SP15 在这里指什么

| 名称 | OASIS 里的名字 | 说明 |
| --- | --- | --- |
| SP15 日前电价 | `TH_SP15_GEN-APND` | 枢纽电价，含 LMP、MCC、MCE、MCL、MGHG |
| 南部负荷电价 | `DLAP_SCE-APND`、`DLAP_SDGE-APND`、`DLAP_VEA-APND` | SCE、SDG&E、Valley Electric |
| 南部辅助服务 | `AS_SP26` | 现货里没有叫 SP15 的辅助服务区。Path 26 以南就是这个区 |
| Path 26 | Midway–Vincent 500kV | SP15 和 ZP26 之间的运行边界，影子价格标成 `sp15` |
| Path 15 | Gates–Midway 一带 | 枢纽名字的来源，影子价格标成 `path15`，默认和 SP15 一起返回 |

南部联络线包括 Palo Verde、Delaney、Hassayampa、North Gila、Blythe、Eldorado、Mead、Marketplace、Adelanto、IPP DC、Victorville、Sylmar、IID、VEA、Silver Peak 和 CFE。Malin、NOB、COI、Tracy 这些北部断面没有收进来。完整名单在 `list_catalog`。

`region_tag` 是按约束名字做的地名分类，原始名字原样保存。`query_shadow_prices` 的 `region=all` 可以看到当天披露的全部日前支路约束，不只有南部。

影子价格只在**绑定**的小时出现。空值不是 0 美元。

方向 `I` 是进口到 CAISO，`E` 是从 CAISO 出口。OASIS 把 `OTC_MW` 标成 Hourly TTC，把 `TTC_MW` 标成 Seasonal TTC。`useage_mw` 沿用他们的拼写，意思是未安排的输电权容量。

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m sp15_oasis sync
```

第一次同步大约要几十分钟。请求之间停 7 秒，这是为了待在 CAISO 的可接受使用范围里。不要把 `--sleep` 改小，也不要几个人同时对 OASIS 做全量同步。一个人同步完，把 `data/sp15.sqlite` 拷给别人即可。

每天补数再跑一次同一条命令。已经结束的历史块会跳过，只刷新还包含今天的那一块。

只补某一张表：

```bash
.venv/bin/python -m sp15_oasis sync --dataset dam_lmp
.venv/bin/python -m sp15_oasis status
```

数据库在 `data/sp15.sqlite`，不进 Git。换路径用环境变量 `SP15_DB`。

## 接到 Cursor

把下面放进 Cursor 的 MCP 配置，路径改成自己的克隆目录。改完后重载 MCP。

```json
{
  "mcpServers": {
    "caiso-sp15": {
      "command": "/ABS/PATH/TO/repo/.venv/bin/python",
      "args": ["-m", "sp15_oasis"],
      "env": { "SP15_ROOT": "/ABS/PATH/TO/repo" }
    }
  }
}
```

服务走 stdio，只在本机查询本地库，不会把 OASIS 再包成一个公开网站。

从零安装、同步和接到 Cursor 见 [MCP使用指南](MCP使用指南.md)。字段中文名、OASIS 原名和单位见 [数据指标对照表](数据指标对照表.md)。

每天 01:15（这台电脑的本地时间）自动补当天已经发布的数据。入库成功和缺数都会在这台 Mac 上弹通知；缺了会持续补到 02:00：

```bash
./scripts/install-daily-sync.sh
```

## 工具

- `list_catalog`：节点、联络线、单位、库里有多少天
- `dataset_coverage`：每张表的起止运行日和同步进度
- `query_dam_prices`：日前电价，美元/MWh
- `query_ancillary`：AS_SP26 日前价格（美元/MW）、需求或采购结果（MW）
- `query_load`：小时负荷预测、实际负荷、日峰预测，MW
- `query_renewables`：风光日前预测、实际出力，以及全网合计，MW
- `query_fuel`：燃料区燃气价格，美元/mmBtu
- `query_ghg`：加州碳配额价格指数
- `query_system_schedule`：日前系统发用电计划，南部区是 `TAC_SOUTH`
- `query_report`：`disclosure` 里的其余报表。`report` 用对照表里的名字，例如 `lmp_rtm_5min`、`load_rtpd`
- `list_weather_datasets`、`query_weather_forecast`：Open-Meteo 的 GFS 点预报。不在 `data/sp15.sqlite`
- `query_tie_atc`：南部联络线日前 ATC，MW
- `query_tie_usage`：南部联络线日前 TTC、OTC、计划潮流、TRM
- `query_shadow_prices`：日前支路/诺模图或联络线约束影子价格
- `training_panel`：事后同小时关联表，不是防泄漏预测训练集。预测训练用下面的 `research_*`
- `query_sql`：一条只读 SELECT
- `research_catalog`、`research_training`、`research_prediction_inputs`、`research_predictions`、`research_metrics`：冻结研究分区。读的是 `SP15_RESEARCH_ROOT` 指向的实验，不是这份 OASIS 档案

日期都是标的运行日 `YYYY-MM-DD`，含首尾。每一行还有 `issued_on`（预测日期）：标的日 10 月 10 日的日前数据是 10 月 9 日预测的，提前两天是 10 月 8 日，提前七天是 10 月 3 日。实测的预测日期等于标的日。`training_panel` 一次最多 5000 小时，用 `offset` 翻页。气象查询的 `end` 不含当天，和上面的电价日期不同。

01:15 这一轮采全的标准：日前电价、AS 价格与需求、南部联络线、CAISO/SCE/SDG&E 日前负荷，以及 SP15 风电和光伏日前预测都有完整小时。实际负荷和实际风光要等运行日走完才齐，不拿来判断这一轮缺不缺。

导出整段训练表：

```bash
.venv/bin/python -m sp15_oasis export \
  --start 2024-01-01 --end 2024-12-31 \
  --out data/sp15_2024.csv
```

`data/*.csv` 被 git 忽略。

主干联络线列是 Palo Verde、Eldorado、Mead、IPP DC–Adelanto、North Gila、Blythe、Sylmar、CFE。`ties=ALL` 会把目录里的南部联络线都摊开。列名 `_i` 是进口，`_e` 是出口，`_atc` 是可用容量，`_ene` 是计划净交换。

## 报表

结构化表来自 `https://oasis.caiso.com/oasisapi/SingleZip`。电价和边界是 DAM。负荷和风光同时有预测和实际值。公开报价走 `GroupZip`。

5 分钟和 15 分钟电价只保留 SP15 的 4 个节点。全机组的期望电量和调度指令没有整库接入。`disclosure` 的日常同步只刷新最近两个运行日；从 `2023-08-01` 补历史要加 `--archive`。结构化表字段、`disclosure` 的 `report` 名，以及气象变量和地点见 [数据指标对照表](数据指标对照表.md)。

| 本地表 | OASIS 报表 | 内容 |
| --- | --- | --- |
| `dam_lmp` | `PRC_LMP` v12 | 四个节点的日前电价和分量 |
| `as_price` | `PRC_AS` v12 | AS_SP26 出清价 |
| `as_requirement` | `AS_REQ` v1 | AS_SP26 需求 |
| `tie_atc` | `TRNS_ATC` v1 | 南部联络线 ATC |
| `tie_usage` | `TRNS_USAGE` v1 | 南部联络线容量和计划潮流 |
| `intertie_shadow` | `PRC_CNSTR` v1 | 联络线约束影子价格，南部打了 `sp15_related` |
| `nomogram_shadow` | `PRC_NOMOGRAM` v1 | 支路和诺模图影子价格，带 `region_tag` |
| `load` | `SLD_FCST` v1 | 日前、提前两天、提前七天负荷预测，以及实际小时负荷 |
| `load_peak` | `SLD_FCST_PEAK` v1 | 各 TAC 区日峰负荷预测 |
| `renewable` | `SLD_REN_FCST` v1 | 风光日前预测和实际出力，含 SP15 |
| `wind_solar_summary` | `ENE_WIND_SOLAR_SUMMARY` v5 | 全网风光合计 |
| `fuel_price` | `PRC_FUEL` v1 | 燃料区燃气价格 |
| `ghg_allowance` | `PRC_GHG_ALLOWANCE` v1 | 加州碳配额价格指数 |
| `as_result` | `AS_RESULTS` v1 | AS_SP26 日前采购结果 |
| `system_schedule` | `ENE_SLRS` v1 | 日前系统负荷、发电、进出口 |
| `disclosure` | 多个报表，见对照表 | 实时、HASP、全联络线、EIM、CRR、延迟报价、名录。用 `query_report` |

气象是另一份库，默认 `/Users/jins/Documents/ChatGPT/比赛/mcp_service/runtime/caiso.sqlite`，可用 `SP15_WEATHER_DB` 换路径。变量是气温、10 米风速、短波辐照、云量和降水，7 个代表点。`watch` 会先拉一轮实时快照，再补 OASIS。

如果以后从批量站点拿到同样表头的 CSV，可以叠进已有的库：

```bash
.venv/bin/python -m sp15_oasis import-csv dam_lmp /path/to/PRC_LMP.csv
```

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

测试不访问 OASIS。
