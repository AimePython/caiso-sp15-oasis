# CAISO SP15 MCP 使用指南

同组的人用这份本地库训练模型，数据是 CAISO SP15 日前市场。下面按顺序做。每一步都可以整段复制。

仓库地址：https://github.com/AimePython/caiso-sp15-oasis

## 1. 装完能拿到什么

两样东西：

1. 本机上的一个 SQLite 文件：`data/sp15.sqlite`。大约 751MB。它不在 Git 里，`git clone` 不会带上它。
2. Cursor 里的一个本机 MCP，名字是 `caiso-sp15`。对话时让它查这个库。查数不会再去访问 CAISO 网站。

这台机器上现有的库，运行日是 **2023-08-01 到 2026-11-08**，时区 **America/Los_Angeles**。运行日是加州电力市场的那一天，写成 `YYYY-MM-DD`，开始和结束都包含当天。

CAISO 在线接口大约只保留 **39 个月**。更早的电价在 https://oasis-bulk.caiso.com/ ，要用你自己的 AWS 账号，流量由你付。这个工具不会去下载那个桶。

## 2. 数据从哪来

优先向已经同步过的同事要文件，不要全组一起向 CAISO 拉数。

**(A) 拷贝，优先用这个。** 向同事要 `data/sp15.sqlite`，放进自己仓库的 `data/` 目录。见第 6 节。

**(B) 自己同步。** 只有没人能给你文件时才用。CAISO 会限流。程序每次请求至少隔 **7 秒**。从 2023-08-01 同步到今天大约 **70 分钟**。不要把 `--sleep` 改小，也不要在别人正在同步时再开一次全量同步。

每天更新用同一条 sync 命令。已经下完的历史块会跳过。

## 3. 先装环境

组里用 Mac。先做 macOS。Windows 在本节最后，步骤更短。

### 3.1 打开终端

打开「终端」（Terminal）。后面的命令都粘贴进去，回车执行。

每一条命令都在**仓库根目录**里执行。根目录里能看到 `src/sp15_oasis`。确认：

```bash
ls src/sp15_oasis
```

应能看到 `cli.py`、`server.py`。如果提示 `No such file or directory`，先做第 4 节，再回到这里。

### 3.2 Git

```bash
git --version
```

应看到类似 `git version 2.x.x`。

如果提示 `command not found`：

```bash
xcode-select --install
```

会弹出安装窗口，点安装，等它结束。关掉终端再打开，重新执行 `git --version`。

已经在用 Homebrew 的人，也可以 `brew install git`。没有 Homebrew 就不用装。

### 3.3 Python 3.11 或更新

不要用 macOS 自带的 Python。到 https://www.python.org/downloads/ 下载 **Python 3.11 或更新** 的 macOS 安装包，打开 pkg 一路安装。安装程序如果有 **Add python to PATH**，勾上。

装完后**新开一个终端窗口**（旧窗口不会拿到新的 PATH），执行：

```bash
python3 --version
```

应看到 `Python 3.11` 或更高，例如 `Python 3.13.x`。

如果提示 `command not found`：完全退出终端（Command+Q），再打开，重试一次。

还是找不到：去 `/Library/Frameworks/Python.framework/Versions/` 看你装的版本号，用那个完整路径。3.13 只是例子，版本号换成你自己的：

```bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 --version
```

后面创建虚拟环境时，把 `python3` 换成这一整行路径。虚拟环境建好之后，其余命令都用 `.venv/bin/python`，不再依赖 `python3` 是否在 PATH 里。

`python3 --version` 如果是 3.9，而且 `which python3` 显示 `/usr/bin/python3`，那是系统自带的，版本不够。改用上面 python.org 安装包里的解释器。本仓库要求 Python `>=3.11`。

### 3.4 Cursor

安装 Cursor 桌面版：打开 https://cursor.com/download ，下载 macOS 安装包，拖进「应用程序」，打开并登录。

### 3.5 Windows（简短）

1. Python：同样从 https://www.python.org/downloads/ 安装 3.11 或更新，勾选 **Add python.exe to PATH**。新开终端执行 `python --version`。
2. Git：没有的话安装 https://git-scm.com/download/win ，新开终端执行 `git --version`。
3. 虚拟环境的命令换成：

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

4. 后面凡是 `.venv/bin/python`，在 Windows 上写成 `.venv\Scripts\python`。MCP 配置里的 `command` 也用这个虚拟环境解释器的绝对路径。

## 4. 拿到代码

```bash
git clone https://github.com/AimePython/caiso-sp15-oasis.git
cd caiso-sp15-oasis
```

应看到克隆结束，并且当前目录名是 `caiso-sp15-oasis`。记住这个目录的绝对路径，第 7 节要填：

```bash
pwd
```

## 5. 建一个本目录里的 Python，并安装

在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

`.venv` 是放在这个文件夹里的一套独立 Python。包装在这里，不用装到系统 Python 上。

成功时：目录里出现 `.venv`，第二条命令结尾有 `Successfully installed`，其中包含这个项目。

检查：

```bash
.venv/bin/python -m sp15_oasis --help
```

应看到子命令 `sync`、`status`、`export`、`import-csv`。

如果 `python3 -m venv` 报错里有 `ensurepip`：回到 https://www.python.org/downloads/ 重装 Python，安装时勾选安装 pip 的选项，然后删掉半成品再来一次：

```bash
rm -rf .venv
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

第 3.3 节如果 `python3` 不在 PATH 里，第一条命令改成你的完整路径，例如：

```bash
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m venv .venv
```

## 6. 拿到数据库

### 6.1 拷贝（优先）

在仓库根目录建立目录，把同事给你的文件放进来，文件名必须是 `sp15.sqlite`：

```bash
mkdir -p data
```

用访达、AirDrop 或 U 盘把文件放到 `data/sp15.sqlite`。大约 751MB。请对方在没有正在跑 sync 的时候拷。如果旁边还有 `sp15.sqlite-wal`，等对方的 sync 结束再拷 `sp15.sqlite`，否则文件可能不完整。

然后：

```bash
.venv/bin/python -m sp15_oasis status
```

健康的输出是一张表，外加下面的 sync chunks。行数会随以后的每日同步增加。这台机器在 2026-11-08 的样子是：

```text
table                        rows  operating days
dam_lmp_sp15_hub            28705  2023-08-01 .. 2026-11-08  (1196 days)
dam_lmp_rows               574100  2023-08-01 .. 2026-11-08  (1196 days)
as_price                   114820  2023-08-01 .. 2026-11-08  (1196 days)
as_requirement             229640  2023-08-01 .. 2026-11-08  (1196 days)
tie_atc                   1569260  2023-08-01 .. 2026-11-08  (1192 days)
tie_usage                 1569260  2023-08-01 .. 2026-11-08  (1192 days)
intertie_shadow             18500  2023-08-01 .. 2026-11-08  (827 days)
nomogram_shadow            204904  2023-08-01 .. 2026-11-08  (1196 days)

sync chunks
  as_price           ok       39 chunks  ...
  as_requirement     ok       39 chunks  ...
  dam_lmp            ok       39 chunks  ...
  intertie_shadow    ok       39 chunks  ...
  nomogram_shadow    ok       39 chunks  ...
  tie_atc            ok       39 chunks  ...
  tie_usage          ok       39 chunks  ...
```

怎么读：

- 电价表（`dam_lmp_*`、`as_price`、`as_requirement`）和 `nomogram_shadow` 的运行日从 `2023-08-01` 覆盖到库里的最后一天。
- `tie_atc`、`tie_usage` 少 4 天，是下面的已知缺口，不是同步失败。
- `intertie_shadow` 的天数更少，因为影子价格只在披露为绑定的小时才有记录。
- sync chunks 的状态应是 `ok`。右边的日期是 31 天一块的结束边界，可以比最后一条运行日更晚。数据到哪一天，看上面的 operating days。

如果提示 `还没有本地库`：文件不在 `data/sp15.sqlite`，或当前目录不是仓库根目录。

### 6.2 自己同步

在仓库根目录：

```bash
.venv/bin/python -m sp15_oasis sync
```

终端会持续打印进度，例如：

```text
dam_lmp 2023-08-01 .. 2023-09-01 下载中
  写入 …… 行
```

大约 70 分钟。可以 Ctrl+C 停下，之后再执行同一条命令。已经完成的块会跳过，并出现类似：

```text
dam_lmp 跳过已完成的 …… 块。加 --refresh 可重下。
```

不要加 `--refresh`，除非你确实要整段重下。不要改小 `--sleep`（默认 7 秒）。

每天补数也是这条 `sync`。它会跳过已结束的历史块，并刷新还包含今天的那一块。

### 6.3 每天 01:15 自动补数

在仓库根目录执行一次：

```bash
./scripts/install-daily-sync.sh
```

这会在这台 Mac 上登记一个定时任务，每天本地时间 01:15 执行 `python -m sp15_oasis watch`。它先跑上面的 `sync`：已结束的历史块会跳过，只刷新还包含今天的那一块，也就是当时 OASIS 已经发布出来的数据。

采全的标准是这一天的日前电价、辅助服务价格、辅助服务需求和南部联络线都有完整小时（夏令时开始那天 23 小时，结束那天 25 小时，其余 24 小时）。影子价格只在绑定的小时才有，不拿来判断缺数据。2026-05-01 到 2026-05-04 的 ATC 和断面使用是源数据缺口，不会因此一直重试。

如果 01:15 这一轮没采全，会弹出一条通知，然后大约每 90 秒再补一次，直到本地时间 02:00。中途补齐会再通知一次。到 02:00 仍然缺数据，会把缺了什么再通知一次，然后停止。日志写在 `data/sync.log`，不会进 Git。

电脑在 01:15 必须是醒着并登录着的。睡着错过的那次不会补跑，醒来后可以自己执行一次 6.2 的命令。

卸掉定时任务：

```bash
./scripts/install-daily-sync.sh --uninstall
```

已知缺口：运行日 **2026-05-01 到 2026-05-04** 有电价和影子价格，没有输电 ATC，也没有断面使用（`tie_atc`、`tie_usage` 这两天范围是空的）。这是 OASIS 源数据的洞。重跑 sync 也不会把这 4 天的 ATC 补出来。

## 7. 接到 Cursor

用 Cursor 打开这个仓库文件夹（File → Open Folder）。

MCP 配置如下。两处路径都换成第 4 节 `pwd` 打出来的绝对路径。`command` 必须是虚拟环境里的 Python，也就是该目录下的 `.venv/bin/python`。

```json
{
  "mcpServers": {
    "caiso-sp15": {
      "command": "/ABS/PATH/TO/caiso-sp15-oasis/.venv/bin/python",
      "args": ["-m", "sp15_oasis"],
      "env": { "SP15_ROOT": "/ABS/PATH/TO/caiso-sp15-oasis" }
    }
  }
}
```

把两处 `/ABS/PATH/TO/caiso-sp15-oasis` 都换成 `pwd` 的输出，不要留着这串占位符。Windows 的 `command` 用 `.venv\Scripts\python` 的绝对路径，反斜杠在 JSON 里写成 `\\`。

贴到哪里，二选一：

- Cursor Settings → MCP，编辑 MCP 配置。
- 或者在仓库里新建 `.cursor/mcp.json`，把上面的 JSON 整段放进去。`.cursor/` 已在 `.gitignore` 里，这个文件不会被提交。

保存后，在 MCP 面板里把 `caiso-sp15` 关掉再打开，或点重载。

成功时，服务器名是 `caiso-sp15`，工具列表是这 9 个：

- `list_catalog`
- `dataset_coverage`
- `query_dam_prices`
- `query_ancillary`
- `query_tie_atc`
- `query_tie_usage`
- `query_shadow_prices`
- `training_panel`
- `query_sql`

红点或报错见第 10 节。

## 8. 在 Cursor 对话里取数

打开本仓库，在 Agent 对话里粘贴下面的话。日期是运行日，`YYYY-MM-DD`，含首尾，时区 America/Los_Angeles。

对话一次能拿回的行数有上限。电价和联络线查询默认 200 行、最多 2000 行。`training_panel` 默认 168 小时、最多 5000 小时，更早的小时用 `offset` 翻页。整段落成 CSV 用第 9 节。

读结果时：

- 电价是美元/MWh。辅助服务价格是美元/MW。潮流、ATC 是 MW。
- OASIS 把电价那一列叫 `MW`。这个库里存成 `value`。
- 方向 `I` 是进口到 CAISO，`E` 是从 CAISO 出口。
- 影子价格空着，表示那个小时没有把这条约束披露为绑定。空不是 0 美元。训练时不要未经说明就填成 0。

**(a) 看覆盖范围**

```text
请使用 caiso-sp15 这个 MCP，调用 dataset_coverage。用中文说明每张表的行数、最早和最晚运行日，以及 sync chunks 是否都是 ok。tie_atc 和 tie_usage 如果比电价少 4 天，请注明是 2026-05-01 到 2026-05-04 的已知缺口。
```

**(b) 拉一周的 SP15 日前电价**

节点 `TH_SP15_GEN-APND` 就是 SP15 枢纽电价。7 天 × 24 小时 = 168 行，`limit` 200 够用。

```text
请使用 caiso-sp15 这个 MCP，调用 query_dam_prices。node 用 TH_SP15_GEN-APND，component 用 ALL，start 用 2024-07-01，end 用 2024-07-07，limit 用 200。用中文表格给出每天的 LMP，单位美元/MWh，并说明 MCC、MCE、MCL、MGHG 各是什么列。
```

**(c) 看一个月的训练表**

2024 年 7 月是 744 个小时，低于 5000 的上限。这一步是让 MCP 说明表结构。要 CSV 文件用第 9 节，不要让对话把整月数字全贴出来。

```text
请使用 caiso-sp15 这个 MCP，调用 training_panel。start 用 2024-07-01，end 用 2024-07-31，ties 用 MAJOR，limit 用 800。先用中文说明这一小时一行里有哪些列（SP15 电价、南部聚合点、AS_SP26、影子价格、主要联络线）。再给 3 行样例。影子价格空值表示该小时没有披露为绑定，不要填成 0。
```

**(d) 查 Palo Verde 的 ATC**

Palo Verde 的 `ti_id` 是 `PALOVRDE_ITC`。3 天、两个方向是 144 行。

```text
请使用 caiso-sp15 这个 MCP，调用 query_tie_atc。ti_id 用 PALOVRDE_ITC，direction 用 ALL，start 用 2024-07-01，end 用 2024-07-03，limit 用 200。用中文说明结果。I 是进口到 CAISO，E 是出口，单位是 MW。
```

## 9. 不用对话，直接导出 CSV

在仓库根目录：

```bash
.venv/bin/python -m sp15_oasis export --start 2024-01-01 --end 2024-12-31 --out data/sp15_2024.csv
```

成功时终端出现：

```text
wrote …… hours to data/sp15_2024.csv
```

`data/*.csv` 在 `.gitignore` 里，不会被提交。换年份就改 `--start`、`--end` 和文件名。日期同样是运行日，含首尾。

## 10. 出问题了怎么办

**`command not found`（python3 或 git）**

完全退出终端再打开。Python 仍找不到，用第 3.3 节的完整路径。Git 仍找不到，再执行一次 `xcode-select --install`，等安装窗口结束。

**`python3 -m venv` 报 ensurepip，或 `.venv` 里没有 pip**

从 https://www.python.org/downloads/ 重装 Python，勾选安装 pip。然后 `rm -rf .venv`，从第 5 节重做。

**MCP 是红的，或启动失败**

按这个顺序查：

1. `command` 是不是仓库里 `.venv/bin/python` 的绝对路径。写成 `python3` 或 `/usr/bin/python3` 会找不到模块。
2. 第 5 节的 `.venv/bin/python -m pip install -e .` 有没有成功。在终端执行 `.venv/bin/python -c "import sp15_oasis"`，没有输出就是安装好了。如果报 `No module named sp15_oasis`，回到第 5 节。
3. `SP15_ROOT` 是不是仓库根目录的绝对路径，和 `command` 里的仓库是同一个。错了会找不到库，或连到别的目录。
4. 改完 JSON 后，关掉再打开 `caiso-sp15`，或重载 MCP。

**查询是空的**

先跑 `.venv/bin/python -m sp15_oasis status`。

- 提示还没有本地库：做第 6 节。
- 你要的日期晚于表上的最后一天：sync 还没走到那天，或今天的块还没刷新。等 sync 结束，或自己执行一次第 6.2 节的命令。
- 要的是 2026-05-01 到 2026-05-04 的 ATC 或断面使用：源数据没有，换日期。
- 影子价格很多空行：那些小时没有披露为绑定，空不是 0。

**同步时报 CAISO 429 或 `CAISO rate limit`**

别人也在同步，或请求太密。停下来，不要减小 `--sleep`。等一段时间后重新执行：

```bash
.venv/bin/python -m sp15_oasis sync
```

已完成的块会跳过。能向同事拷到 `data/sp15.sqlite` 就不要自己重跑全量。
