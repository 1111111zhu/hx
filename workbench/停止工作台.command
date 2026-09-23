#!/bin/bash
# 华鑫医药工作台 —— 停止后台服务。
#
# 正常情况下在启动终端按 Ctrl+C 即可；当终端已被关掉、只留下服务进程时，
# 双击本文件把残留服务停干净（含端口文件与 pid 文件）。
#
# 等价于：bash workbench/停止工作台.command

set -u

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT_FILE="$WORKBENCH_DIR/runs/server.port"
PID_FILE="$WORKBENCH_DIR/runs/server.pid"

echo "=============================================================="
echo "  停止华鑫医药工作台"
echo "=============================================================="

FOUND=0

# 1) 按 pid 文件停
if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    echo "停止 pid $PID …"
    kill "$PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$PID" 2>/dev/null || break
      sleep 0.2
    done
    kill -9 "$PID" 2>/dev/null || true
    FOUND=1
  else
    echo "pid 文件里的进程已不在（$PID）。"
  fi
fi

# 2) 兜底：端口文件里的端口若仍有监听，找到占用进程并停掉
if [ -f "$PORT_FILE" ]; then
  PORT="$(cat "$PORT_FILE" 2>/dev/null || true)"
  if [ -n "$PORT" ] && curl -sS -m 2 -o /dev/null "http://127.0.0.1:$PORT/api/frameworks" 2>/dev/null; then
    echo "端口 $PORT 上仍有工作台在响应，尝试停止…"
    PIDS="$(pgrep -f "workbench/server.py" 2>/dev/null || true)"
    if [ -n "$PIDS" ]; then
      # shellcheck disable=SC2086
      kill $PIDS 2>/dev/null || true
      sleep 1
      # shellcheck disable=SC2086
      kill -9 $PIDS 2>/dev/null || true
      FOUND=1
    fi
  fi
fi

# 3) 最后兜底：按进程名清理
REMAIN="$(pgrep -f "workbench/server.py" 2>/dev/null || true)"
if [ -n "$REMAIN" ]; then
  echo "仍有残留进程：$REMAIN，正在停止…"
  # shellcheck disable=SC2086
  kill $REMAIN 2>/dev/null || true
  sleep 1
  REMAIN="$(pgrep -f "workbench/server.py" 2>/dev/null || true)"
  if [ -n "$REMAIN" ]; then
    # shellcheck disable=SC2086
    kill -9 $REMAIN 2>/dev/null || true
  fi
  FOUND=1
fi

rm -f "$PORT_FILE" "$PID_FILE"

if [ "$FOUND" -eq 1 ]; then
  echo "工作台已停止。"
else
  echo "没有发现正在运行的工作台。"
fi

# 从 Finder 双击运行时，让窗口留一会儿再关，避免看不到结果
if [ -t 0 ]; then :; else
  echo "按回车键关闭本窗口。"; read -r _ || true
fi
