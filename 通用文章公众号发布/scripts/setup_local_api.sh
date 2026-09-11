#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}

echo "通用文章外发：本机公众号 API 初始化"
echo "只会配置本机凭证和检查 API，不会发布文章。"
"$PYTHON_BIN" "$SCRIPT_DIR/wechat_draft_api.py" configure
"$PYTHON_BIN" "$SCRIPT_DIR/wechat_draft_api.py" check-auth
echo "初始化完成。创建草稿前仍需在 Codex 中明确确认。"
