#!/bin/bash
# Register a launchd job that refreshes the local OASIS database every day at 01:15.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
LABEL="com.aimepython.caiso-sp15-oasis.sync"
DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

unload() {
  launchctl bootout "${DOMAIN}/${LABEL}" 2>/dev/null || true
}

if [[ "${1:-}" == "--uninstall" ]]; then
  unload
  rm -f "$DEST"
  echo "removed ${LABEL}"
  exit 0
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "找不到 ${PYTHON}。先在仓库根目录执行：python3 -m venv .venv && .venv/bin/python -m pip install -e ." >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/data"

cat > "$DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON}</string>
    <string>-m</string>
    <string>sp15_oasis</string>
    <string>watch</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>SP15_ROOT</key>
    <string>${ROOT}</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>1</integer>
    <key>Minute</key>
    <integer>15</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${ROOT}/data/sync.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/data/sync.log</string>
</dict>
</plist>
EOF

unload
launchctl bootstrap "$DOMAIN" "$DEST"
launchctl enable "${DOMAIN}/${LABEL}"
echo "已登记：每天本地时间 01:15 开始补采，没采全会提醒，并持续补到 02:00"
echo "任务文件：${DEST}"
echo "日志：${ROOT}/data/sync.log"
