#!/bin/bash
# 华鑫医药工作台 —— 双击即可启动
#   1) 启动本地服务（端口从 8765 起，占用自动顺延）
#   2) 等真实端口就绪后打开浏览器
#   3) 检查 dsh 是否可用（可选拉起 dsh 会话：WORKBENCH_BOOT_DSH=1）
#   4) 检查微信公众号 API 状态，未配置就拉起仓库既成的配置终端
# 停止：在本终端窗口按 Ctrl+C。

set -u

WORKBENCH_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$WORKBENCH_DIR")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PORT_FILE="$WORKBENCH_DIR/runs/server.port"
WECHAT_API="$REPO_ROOT/通用文章公众号发布/scripts/wechat_draft_api.py"
WECHAT_SETUP="$REPO_ROOT/通用文章公众号发布/scripts/setup_local_api.sh"

cd "$REPO_ROOT" 2>/dev/null || { echo "无法进入仓库目录：$REPO_ROOT"; exit 1; }
mkdir -p "$WORKBENCH_DIR/runs"
rm -f "$PORT_FILE"

echo "=============================================================="
echo "  华鑫医药工作台"
echo "  仓库: $REPO_ROOT"
echo "=============================================================="

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "错误：找不到 $PYTHON_BIN。请先安装 Python 3。"
  echo "按回车键关闭本窗口。"; read -r _; exit 1
fi
echo "Python: $("$PYTHON_BIN" --version 2>&1)"

# ---------- 1) 启动服务 ----------
"$PYTHON_BIN" "$WORKBENCH_DIR/server.py" --port 8765 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' INT TERM EXIT

# ---------- 2) 等端口文件，拿到真实端口 ----------
PORT=""
for _ in $(seq 1 150); do
  if [ -f "$PORT_FILE" ]; then
    PORT="$(cat "$PORT_FILE" 2>/dev/null || true)"
    [ -n "$PORT" ] && break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "错误：服务进程已退出，未能启动。"
    echo "按回车键关闭本窗口。"; read -r _; exit 1
  fi
  sleep 0.1
done

if [ -z "$PORT" ]; then
  echo "错误：等待端口就绪超时（15 秒）。"
  echo "按回车键关闭本窗口。"; read -r _; exit 1
fi

URL="http://127.0.0.1:$PORT/"
echo "服务地址: $URL"
open "$URL" 2>/dev/null || echo "（无法自动打开浏览器，请手动访问上面的地址）"

# ---------- 3) dsh 可用性 ----------
DSH_BIN="${DSH_BIN:-/opt/homebrew/bin/dsh}"
if [ ! -x "$DSH_BIN" ]; then
  if command -v dsh >/dev/null 2>&1; then
    DSH_BIN="$(command -v dsh)"
  fi
fi

if [ -x "$DSH_BIN" ]; then
  echo "dsh: 可用 -> $DSH_BIN ($("$DSH_BIN" --version 2>/dev/null | head -n 1))"
  # 默认 auto：没有 dsh 在跑就拉起一个会话；已经在跑（例如 dsh web 占了 3080）就跳过，避免抢端口。
  # 可用 WORKBENCH_BOOT_DSH=1 强制拉起，或 =0 完全跳过。
  DSH_BOOT="${WORKBENCH_BOOT_DSH:-auto}"
  DSH_WEB_URL="${DSH_WEB_URL:-http://127.0.0.1:3080}"
  if [ "$DSH_BOOT" = "0" ]; then
    echo "dsh: WORKBENCH_BOOT_DSH=0，跳过拉起；卡片「启动」时按需调用。"
  elif [ "$DSH_BOOT" != "1" ] && curl -sS -m 2 -o /dev/null "$DSH_WEB_URL" 2>/dev/null; then
    echo "dsh: 检测到 $DSH_WEB_URL 已有 dsh 在运行，跳过拉起以免端口冲突。"
    echo "     如需强制再开一个会话，设 WORKBENCH_BOOT_DSH=1 后重新启动。"
  else
    echo "dsh: 在新终端里拉起 dsh 会话…"
    osascript -e "tell application \"Terminal\" to do script \"cd '$REPO_ROOT' && '$DSH_BIN'\"" \
      >/dev/null 2>&1 || echo "dsh: 无法自动打开终端，请手动运行 $DSH_BIN"
  fi
else
  echo "dsh: 【不可用】找不到 $DSH_BIN。工作台仍会启动，但卡片「启动」会失败；"
  echo "     可在页面的「运行环境」里填写真实 dsh 路径。"
fi

# ---------- 4) 微信公众号 API 状态 ----------
if [ -f "$WECHAT_API" ]; then
  echo "微信 API: 正在检查 check-auth（最多等 20 秒）…"
  WECHAT_LOG="$WORKBENCH_DIR/runs/wechat-check.log"
  "$PYTHON_BIN" "$WECHAT_API" check-auth >"$WECHAT_LOG" 2>&1 &
  WECHAT_PID=$!

  WAITED=0
  while kill -0 "$WECHAT_PID" 2>/dev/null && [ "$WAITED" -lt 80 ]; do
    sleep 0.25
    WAITED=$((WAITED + 1))
  done

  if kill -0 "$WECHAT_PID" 2>/dev/null; then
    echo "微信 API: 检查仍在进行（网络较慢）。工作台照常启动，稍后在页面上点「刷新状态」。"
  else
    wait "$WECHAT_PID"
    WECHAT_RC=$?
    if [ "$WECHAT_RC" -eq 0 ]; then
      echo "微信 API: 已连接（check-auth 通过）"
    else
      echo "微信 API: 未配置或连接失败 —— 正在打开配置终端…"
      sed -n '1,5p' "$WECHAT_LOG" 2>/dev/null
      if [ -f "$WECHAT_SETUP" ]; then
        open -a Terminal "$WECHAT_SETUP" 2>/dev/null \
          || echo "微信 API: 无法自动打开终端，请手动运行：sh $WECHAT_SETUP"
      fi
      echo "微信 API: 配置完成后回到工作台页面点「刷新状态」即可。"
    fi
  fi
else
  echo "微信 API: 找不到 $WECHAT_API，跳过检查。"
fi

echo "--------------------------------------------------------------"
echo "工作台已就绪。按 Ctrl+C 停止服务。"
echo "--------------------------------------------------------------"

# ---------- 5) 前台驻留 ----------
wait "$SERVER_PID"
echo "服务已停止。"
