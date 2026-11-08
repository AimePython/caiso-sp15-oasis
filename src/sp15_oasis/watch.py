"""Retry the daily sync until 02:00 local time, and say so when a day is short."""

from __future__ import annotations

import fcntl
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, time as clock_time
from pathlib import Path

from .calendar import today_pt
from .freshness import day_gaps
from .sync import log, sync_all

Notify = Callable[[str], None]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def run_watch(
    *,
    until: clock_time = clock_time(2, 0),
    pause_seconds: float = 90.0,
    sync: Callable[[], None] = sync_all,
    gaps_for: Callable = day_gaps,
    notify: Notify | None = None,
    clock: Clock | None = None,
    sleeper: Sleep = time.sleep,
) -> int:
    """Sync, then keep syncing until the published day is complete or `until`.

    Returns 0 when the day is complete, 1 when the deadline passes with gaps.
    A second watch exits immediately so two jobs do not hit OASIS together.
    """
    notify = notify or mac_notify
    clock = clock or (lambda: datetime.now().astimezone())
    lock = _acquire_lock()
    if lock is None:
        log("已有补采在跑，这次退出。")
        return 0
    try:
        alerted = False
        while True:
            moment = clock()
            deadline = _deadline(moment, until)
            try:
                sync()
                missing = list(gaps_for(today_pt()))
            except Exception as exc:
                missing = [f"同步失败：{exc}"]
            day = today_pt().isoformat()
            if not missing:
                if alerted:
                    notify(f"运行日 {day} 已补齐。")
                log(f"运行日 {day} 已齐。")
                return 0
            summary = "；".join(missing)
            if moment >= deadline:
                notify(f"运行日 {day} 到 {until.strftime('%H:%M')} 仍未采全：{summary}")
                return 1
            if not alerted:
                notify(f"运行日 {day} 采集不全：{summary}。{until.strftime('%H:%M')} 前会继续补采。")
                alerted = True
            else:
                log(f"运行日 {day} 仍不全：{summary}")
            remaining = (deadline - moment).total_seconds()
            sleeper(min(pause_seconds, max(remaining, 0)))
    finally:
        lock.close()


def mac_notify(message: str) -> None:
    log(message)
    script = (
        "on run argv\n"
        "display notification (item 2 of argv) with title (item 1 of argv)\n"
        "end run"
    )
    subprocess.run(
        ["/usr/bin/osascript", "-e", script, "CAISO SP15", message],
        check=False,
    )


def _deadline(moment: datetime, until: clock_time) -> datetime:
    local = moment.astimezone()
    end = local.replace(hour=until.hour, minute=until.minute, second=0, microsecond=0)
    if local >= end:
        return local
    return end


def _acquire_lock():
    path = Path("/tmp/caiso-sp15-oasis-watch.lock")
    handle = path.open("a", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle
