#!/bin/bash
# 华鑫医药工作台 —— 压缩包解压后的顶层入口。
#
# 真正的工作台在 workbench/ 下；这里只是一个薄封装，
# 让解压后第一眼就能看到可以直接双击的启动文件。
#
# 等价于：bash workbench/启动工作台.command
# 停止：在打开的终端窗口按 Ctrl+C。

set -u

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$REPO_ROOT/workbench/启动工作台.command"

if [ ! -f "$LAUNCHER" ]; then
  echo "错误：找不到 $LAUNCHER"
  echo "请确认压缩包已完整解压（不要直接在压缩包里双击）。"
  echo "按回车键关闭本窗口。"; read -r _; exit 1
fi

if [ ! -x "$LAUNCHER" ]; then
  # 某些解压工具会丢掉可执行位，这里补回来再启动。
  chmod +x "$LAUNCHER" 2>/dev/null || true
fi

exec bash "$LAUNCHER"
