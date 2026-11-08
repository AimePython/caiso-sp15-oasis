"""Command line: sync, status, export, import-csv."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import time as clock_time

from .calendar import RETENTION_FLOOR, parse_day, today_pt
from .db import MissingDatabase, connect, upsert
from .query import dataset_coverage, training_panel
from .sync import SPEC_BY_NAME, sync_all
from .watch import run_watch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sp15_oasis")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sync = sub.add_parser("sync", help="从 OASIS 补数据到本地库")
    sync.add_argument("--start", default=RETENTION_FLOOR.isoformat(), help="起始运行日，含当天")
    sync.add_argument("--end", default=None, help="结束运行日，含当天，默认太平洋时区的今天")
    sync.add_argument("--dataset", action="append", dest="datasets", help="只同步这一张，可重复")
    sync.add_argument("--sleep", type=float, default=7.0, help="两次请求之间至少休息的秒数")
    sync.add_argument("--refresh", action="store_true", help="已完成的历史块也重新下载")

    sub.add_parser("status", help="看每张表覆盖了哪些运行日")

    watch = sub.add_parser("watch", help="补采到本地时间 02:00，没采全就提醒")
    watch.add_argument("--until", default="02:00", help="本地时间，过了这个点还没齐就停，并再提醒一次")
    watch.add_argument("--pause", type=float, default=90.0, help="两次补采之间至少休息的秒数")

    export = sub.add_parser("export", help="把训练表导出成 CSV")
    export.add_argument("--start", required=True)
    export.add_argument("--end", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--ties", default="MAJOR")

    importer = sub.add_parser("import-csv", help="把 OASIS 原始 CSV 导入本地库")
    importer.add_argument("dataset", choices=sorted(SPEC_BY_NAME))
    importer.add_argument("path")

    args = parser.parse_args(argv)
    if args.cmd == "sync":
        end = parse_day(args.end) if args.end else today_pt()
        sync_all(
            start=parse_day(args.start),
            end=end,
            datasets=args.datasets,
            sleep_seconds=args.sleep,
            refresh=args.refresh,
        )
        return 0
    if args.cmd == "status":
        return _status()
    if args.cmd == "watch":
        hour, minute = args.until.split(":", 1)
        return run_watch(until=clock_time(int(hour), int(minute)), pause_seconds=args.pause)
    if args.cmd == "export":
        return _export(args.start, args.end, args.out, args.ties)
    if args.cmd == "import-csv":
        return _import_csv(args.dataset, args.path)
    parser.error(f"未知命令 {args.cmd}")
    return 2


def _status() -> int:
    try:
        payload = dataset_coverage()
    except MissingDatabase as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{'table':22} {'rows':>10}  operating days")
    for name, info in payload["tables"].items():
        span = f"{info['first_operating_day']} .. {info['last_operating_day']}"
        print(f"{name:22} {info['rows']:10}  {span}  ({info['distinct_days']} days)")
    if payload["sync_chunks"]:
        print("\nsync chunks")
        for chunk in payload["sync_chunks"]:
            print(
                f"  {chunk['dataset']:18} {chunk['status']:6} "
                f"{chunk['chunks']:4} chunks  {chunk['rows']} rows  "
                f"{chunk['first_chunk']} .. {chunk['last_chunk_exclusive']}"
            )
    return 0


def _export(start: str, end: str, out: str, ties: str) -> int:
    offset = 0
    rows: list[dict] = []
    fieldnames: list[str] = []
    while True:
        page = training_panel(start, end, ties=ties, limit=5000, offset=offset)
        batch = page["rows"]
        if not batch:
            break
        if not fieldnames:
            fieldnames = list(batch[0])
        for row in batch:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        rows.extend(batch)
        offset += len(batch)
        if offset >= page["meta"]["rows_total"]:
            break
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or ["opr_dt"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} hours to {out}", file=sys.stderr)
    return 0


def _import_csv(dataset: str, path: str) -> int:
    spec = SPEC_BY_NAME[dataset]
    with open(path, newline="", encoding="utf-8-sig") as handle:
        raw = list(csv.DictReader(handle))
    stored = spec.normalize(raw)
    conn = connect(write=True)
    try:
        with conn:
            count = upsert(conn, spec.table, stored)
    finally:
        conn.close()
    print(f"imported {count} rows into {spec.table}", file=sys.stderr)
    return 0
