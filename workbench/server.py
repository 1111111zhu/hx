#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""华鑫医药工作台 —— 本地网页控制台（纯 Python 3 标准库，零第三方依赖）。

功能：
  1. 展示仓库内三个 skill 框架卡片；
  2. 管理 DeepSeek / 微信公众号 两组 API 配置（config.json，密钥打码回显）；
  3. 以 `dsh --profile headless "<提示词>"` 子进程方式启动 one-shot 任务，
     把 stdout/stderr 流式落盘，供前端轮询 /api/run/<id> 回显。

启动：
    python3 workbench/server.py                # 默认 8765，占用自动顺延
    python3 workbench/server.py --port 9000 --open

仅监听 127.0.0.1，不对外暴露。
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------
# 路径常量
# --------------------------------------------------------------------------

WORKBENCH_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(WORKBENCH_DIR)
RUNS_DIR = os.path.join(WORKBENCH_DIR, "runs")
CONFIG_PATH = os.path.join(WORKBENCH_DIR, "config.json")
EXAMPLE_CONFIG_PATH = os.path.join(WORKBENCH_DIR, "config.example.json")
PORT_FILE = os.path.join(RUNS_DIR, "server.port")

DEFAULT_PORT = 8765
PORT_SCAN_LIMIT = 100
MAX_RUNS_KEPT = 200

# 微信公众号凭证：完全复用仓库既成机制，工作台不另建存储。
WECHAT_API_SCRIPT_REL = "通用文章公众号发布/scripts/wechat_draft_api.py"
WECHAT_SETUP_SCRIPT_REL = "通用文章公众号发布/scripts/setup_local_api.sh"
WECHAT_KEYCHAIN_SERVICE = "codex-wechat-article"

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}

# --------------------------------------------------------------------------
# 框架（skill 包）元信息
# --------------------------------------------------------------------------
# prompt 模板中的 {skill} 会被替换为该 skill 的 SKILL.md 相对路径。

FRAMEWORKS = [
    {
        "key": "weekly-report",
        "name": "周报制作",
        "dir": "周报制作",
        "skill": "周报制作/SKILL.md",
        "summary": (
            "刷新一套已配对的华鑫医药周报 PPTX / XLSX，或其中某个板块"
            "（研究成果、政府政策、行业新闻、公司公告）。"
            "产出仍是一对可编辑的 Office 文件，保留原生表格、Excel 证据链与模板版式。"
        ),
        "prompt": "先读取 {skill}，再执行周报更新：按该 skill 的输入契约刷新配对交付的 PPTX 与 XLSX。",
        "hint": "只更新行业新闻时，可改读 周报制作/行业新闻专项包/SKILL.md。",
    },
    {
        "key": "weekly-wechat",
        "name": "周报公众号发布",
        "dir": "周报公众号发布",
        "skill": "周报公众号发布/SKILL.md",
        "summary": (
            "把华鑫医药周报 PPTX 转成公众号用 Word 文案与完整图片素材包："
            "合规说明图 + 全部报告页 PNG + 唯一的 文字.docx，输出一个按报告日期命名的文件夹。"
        ),
        "prompt": "先读取 {skill}，再生成周报的 Word 文案与图片素材包。",
    },
    {
        "key": "article-wechat",
        "name": "通用文章公众号发布",
        "dir": "通用文章公众号发布",
        "skill": "通用文章公众号发布/SKILL.md",
        "summary": (
            "把研究报告 Word 按固定公众号规则做成合规首图、正文 HTML（可选保存公众号草稿）。"
            "不负责发布文章，也不迁移账号密码。"
        ),
        "prompt": "先读取 {skill}，再执行通用文章的公众号内容制作流程。",
    },
]

# --------------------------------------------------------------------------
# 配置读写
# --------------------------------------------------------------------------

# 注意：微信公众号的 AppID / AppSecret **不存在这里**。
# 它们复用仓库既成的凭证机制（macOS 钥匙串 service=codex-wechat-article，
# 或同名环境变量 WECHAT_OFFICIAL_APP_ID / WECHAT_OFFICIAL_APP_SECRET），
# 由 通用文章公众号发布/scripts/wechat_draft_api.py 负责读写。
# 工作台只调用它的 check-auth 读取状态，从不读出、也不缓存明文密钥。
DEFAULT_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-chat",
    },
    "dsh": {
        "command": "/opt/homebrew/bin/dsh",
        "profile": "headless",
        "extra_args": [],
        "timeout_sec": 0,
    },
    "status": {
        "deepseek": "未连接",
        "deepseek_message": "",
        "wechat": "待配置",
        "wechat_message": "",
    },
}

MASK_CHAR = "\u2022"  # •
CONFIG_LOCK = threading.Lock()


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def mask_secret(value: str) -> str:
    """只回显后 4 位，其余打码。"""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 4 else value
    return MASK_CHAR * 8 + tail


def looks_masked(value: str) -> bool:
    return bool(value) and MASK_CHAR in value


def load_config() -> dict:
    with CONFIG_LOCK:
        raw = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
            except (ValueError, OSError) as exc:
                sys.stderr.write("[workbench] config.json 解析失败，使用默认配置: %s\n" % exc)
                raw = {}
        return _deep_merge(DEFAULT_CONFIG, raw if isinstance(raw, dict) else {})


def save_config(config: dict) -> None:
    with CONFIG_LOCK:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, CONFIG_PATH)
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass


def public_config(config: dict) -> dict:
    """GET /api/config 的返回体：所有 secret 一律打码，微信凭证完全不出现在这里。"""
    deepseek = config.get("deepseek", {})
    dsh = config.get("dsh", {})
    status = config.get("status", {})
    return {
        "deepseek": {
            "base_url": deepseek.get("base_url", ""),
            "api_key": mask_secret(deepseek.get("api_key", "")),
            "api_key_set": bool(deepseek.get("api_key")),
            "model": deepseek.get("model", ""),
        },
        "wechat": {
            # 只暴露状态与脚本位置；AppID/AppSecret 既不在 config.json 里，
            # 也不会经由本接口回传。
            "credential_store": "macOS 钥匙串（service=codex-wechat-article）或同名环境变量",
            "status": status.get("wechat", "待配置"),
            "status_message": status.get("wechat_message", ""),
            "check_script": WECHAT_API_SCRIPT_REL,
            "setup_script": WECHAT_SETUP_SCRIPT_REL,
        },
        "dsh": {
            "command": dsh.get("command", ""),
            "profile": dsh.get("profile", ""),
            "extra_args": dsh.get("extra_args", []),
            "timeout_sec": dsh.get("timeout_sec", 0),
        },
        "status": {
            "deepseek": status.get("deepseek", "未连接"),
            "deepseek_message": status.get("deepseek_message", ""),
            "wechat": status.get("wechat", "待配置"),
            "wechat_message": status.get("wechat_message", ""),
        },
    }


def apply_config_update(incoming: dict) -> dict:
    """把前端提交的配置合并进 config.json。

    - DeepSeek 的 api_key 若为空、或仍是打码串（用户没改动），保留原值。
    - 微信公众号的任何字段一律丢弃：它的凭证只走钥匙串/环境变量。
    """
    current = load_config()
    incoming = incoming or {}

    patch = incoming.get("deepseek")
    if isinstance(patch, dict):
        target = current.setdefault("deepseek", {})
        # 显式清空：前端"清除密钥"按钮提交 clear_api_key=true。
        # 空字符串仍然表示"不修改"，避免页面刷新后误清空。
        if patch.get("clear_api_key"):
            target["api_key"] = ""
        for field, value in patch.items():
            if field == "api_key":
                value = (value or "").strip()
                if not value or looks_masked(value):
                    continue  # 保留已存的真实值
                target[field] = value
            elif field == "clear_api_key":
                continue
            else:
                target[field] = value.strip() if isinstance(value, str) else value

    # 明确拒绝把微信密钥写进 config.json（即使前端被改坏也不会落盘）。
    if "wechat" in current:
        current.pop("wechat", None)

    dsh_patch = incoming.get("dsh")
    if isinstance(dsh_patch, dict):
        target = current.setdefault("dsh", {})
        for field, value in dsh_patch.items():
            if field == "extra_args":
                if isinstance(value, str):
                    value = [part for part in value.split() if part]
                if isinstance(value, list):
                    target[field] = [str(part) for part in value]
            elif field == "timeout_sec":
                try:
                    target[field] = max(0, int(value))
                except (TypeError, ValueError):
                    pass
            elif isinstance(value, str):
                target[field] = value.strip()

    save_config(current)
    return current


# --------------------------------------------------------------------------
# DeepSeek 连通性测试
# --------------------------------------------------------------------------


def test_deepseek(deepseek: dict) -> dict:
    base_url = (deepseek.get("base_url") or DEFAULT_CONFIG["deepseek"]["base_url"]).strip()
    base_url = base_url.rstrip("/")
    api_key = (deepseek.get("api_key") or "").strip()

    if not api_key:
        return {"ok": False, "message": "未填写 DeepSeek API Key。", "models": [], "endpoint": ""}

    candidates = [base_url + "/v1/models", base_url + "/models"]
    last_message = ""
    for endpoint in candidates:
        request = urllib.request.Request(
            endpoint,
            headers={"Authorization": "Bearer " + api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", "replace")
            payload = json.loads(body) if body.strip() else {}
            models = []
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                models = [item.get("id") for item in data if isinstance(item, dict) and item.get("id")]
            return {
                "ok": True,
                "message": "连接成功（HTTP %s），返回 %d 个模型。" % (response.status, len(models)),
                "models": models[:50],
                "endpoint": endpoint,
            }
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001 - 诊断信息尽力而为
                detail = ""
            if exc.code in (401, 403):
                return {
                    "ok": False,
                    "message": "认证失败（HTTP %d）：API Key 无效或无权访问。%s" % (exc.code, detail),
                    "models": [],
                    "endpoint": endpoint,
                }
            if exc.code == 404:
                last_message = "HTTP 404：%s 不存在。" % endpoint
                continue
            return {
                "ok": False,
                "message": "请求失败（HTTP %d）：%s" % (exc.code, detail),
                "models": [],
                "endpoint": endpoint,
            }
        except urllib.error.URLError as exc:
            return {
                "ok": False,
                "message": "网络不可达：%s（base_url 是否正确？本机能否访问外网？）" % exc.reason,
                "models": [],
                "endpoint": endpoint,
            }
        except (ValueError, OSError) as exc:
            return {"ok": False, "message": "响应无法解析：%s" % exc, "models": [], "endpoint": endpoint}

    return {"ok": False, "message": last_message or "所有候选端点均失败。", "models": [], "endpoint": ""}


# --------------------------------------------------------------------------
# 微信公众号：复用仓库既成的钥匙串 / 环境变量凭证机制
# --------------------------------------------------------------------------

WECHAT_NOT_CONFIGURED = "未配置"
WECHAT_OK = "已连接"
WECHAT_FAILED = "连接失败"


def _python_for_scripts() -> str:
    """跑仓库内 python 脚本用的解释器。"""
    if sys.executable and os.path.basename(sys.executable).startswith("python"):
        return sys.executable
    return shutil.which("python3") or "python3"


def wechat_script_paths() -> dict:
    return {
        "api": os.path.join(REPO_ROOT, WECHAT_API_SCRIPT_REL),
        "setup": os.path.join(REPO_ROOT, WECHAT_SETUP_SCRIPT_REL),
    }


def check_wechat_auth() -> dict:
    """运行 `wechat_draft_api.py check-auth` 判断状态。

    绝不读取钥匙串里的值；只看脚本的退出码与它自己打印的信息。
    返回 {status, message, errcode, errmsg, stdout, exit_code}
    """
    paths = wechat_script_paths()
    if not os.path.isfile(paths["api"]):
        return {
            "status": WECHAT_FAILED,
            "message": "找不到 %s（仓库结构是否被改动？）" % WECHAT_API_SCRIPT_REL,
            "errcode": None,
            "errmsg": "",
            "output": "",
            "exit_code": None,
        }

    try:
        result = subprocess.run(
            [_python_for_scripts(), paths["api"], "check-auth"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": WECHAT_FAILED,
            "message": "check-auth 超时（45 秒）：无法访问 api.weixin.qq.com，请检查网络或出口 IP 白名单。",
            "errcode": None,
            "errmsg": "",
            "output": "",
            "exit_code": None,
        }
    except OSError as exc:
        return {
            "status": WECHAT_FAILED,
            "message": "无法运行 check-auth：%s" % exc,
            "errcode": None,
            "errmsg": "",
            "output": "",
            "exit_code": None,
        }

    combined = ((result.stdout or "") + (result.stderr or "")).strip()

    if result.returncode == 0:
        return {
            "status": WECHAT_OK,
            "message": "check-auth 通过，已取得 access_token（值不显示）。",
            "errcode": None,
            "errmsg": "",
            "output": combined,
            "exit_code": 0,
        }

    # 区分「还没配」和「配了但连不上」
    missing = re.findall(r"缺少\s+(WECHAT_OFFICIAL_APP_(?:ID|SECRET))", combined)
    if missing:
        return {
            "status": WECHAT_NOT_CONFIGURED,
            "message": "本机钥匙串与环境变量里都没有 %s。请点「打开配置终端」在终端里交互填写。"
            % "、".join(sorted(set(missing))),
            "errcode": None,
            "errmsg": "",
            "output": combined,
            "exit_code": result.returncode,
        }

    errcode_match = re.search(r"错误\s*(-?\d+)\s*:\s*(.*)", combined)
    errcode = errcode_match.group(1) if errcode_match else None
    errmsg = errcode_match.group(2).strip() if errcode_match else ""

    return {
        "status": WECHAT_FAILED,
        "message": "check-auth 失败（退出码 %s）：%s" % (result.returncode, combined or "无输出"),
        "errcode": errcode,
        "errmsg": errmsg,
        "output": combined,
        "exit_code": result.returncode,
    }


def refresh_wechat_status(config: dict, result: dict) -> dict:
    config.setdefault("status", {})
    config["status"]["wechat"] = result["status"]
    detail = result["message"]
    if result.get("errcode"):
        detail += " [errcode=%s errmsg=%s]" % (result["errcode"], result.get("errmsg", ""))
    config["status"]["wechat_message"] = detail
    save_config(config)
    result["status_message"] = detail
    return result


def open_wechat_setup_terminal() -> dict:
    """在终端里启动 setup_local_api.sh，让用户自己交互输入密钥。

    工作台不经手任何密钥，只负责把终端窗口拉起来。
    """
    paths = wechat_script_paths()
    if not os.path.isfile(paths["setup"]):
        return {"ok": False, "message": "找不到 %s" % WECHAT_SETUP_SCRIPT_REL}

    try:
        os.chmod(paths["setup"], 0o755)
    except OSError:
        pass

    if sys.platform != "darwin":
        return {
            "ok": False,
            "message": "自动开终端目前只实现了 macOS。请手动运行：sh %s" % paths["setup"],
        }

    opened = False
    detail = ""
    # 首选 open -a Terminal：不触发自动化权限弹窗。
    try:
        proc = subprocess.run(
            ["open", "-a", "Terminal", paths["setup"]],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode == 0:
            opened = True
        else:
            detail = (proc.stderr or proc.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        detail = str(exc)

    if not opened:
        # 退路：osascript 开 Terminal 并执行
        script = 'tell application "Terminal" to do script "sh %s"' % paths["setup"].replace('"', '\\"')
        try:
            proc = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True, timeout=20
            )
            opened = proc.returncode == 0
            if not opened:
                detail = (proc.stderr or proc.stdout or "").strip() or detail
        except (OSError, subprocess.SubprocessError) as exc:
            detail = str(exc)

    if opened:
        return {
            "ok": True,
            "message": "已在新终端窗口启动 %s。请在终端里输入 AppID / AppSecret，"
            "完成后回到本页点「刷新状态」。" % WECHAT_SETUP_SCRIPT_REL,
        }
    return {
        "ok": False,
        "message": "无法自动打开终端（%s）。请手动运行：sh %s" % (detail or "未知原因", paths["setup"]),
    }


# --------------------------------------------------------------------------
# dsh 探测
# --------------------------------------------------------------------------


def resolve_dsh(command: str):
    """返回 (可执行路径 or None, 说明)。"""
    command = (command or "").strip() or DEFAULT_CONFIG["dsh"]["command"]
    if os.path.isabs(command) or os.sep in command:
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command, ""
        return None, "找不到可执行文件：%s" % command
    found = shutil.which(command)
    if found:
        return found, ""
    return None, "PATH 中找不到 %s" % command


def dsh_info(config: dict) -> dict:
    dsh = config.get("dsh", {})
    path, problem = resolve_dsh(dsh.get("command", ""))
    info = {
        "command": dsh.get("command", ""),
        "resolved": path or "",
        "available": bool(path),
        "profile": dsh.get("profile", ""),
        "message": problem,
        "version": "",
        "profiles": [],
    }
    if not path:
        return info
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=15
        )
        info["version"] = (result.stdout or result.stderr or "").strip().splitlines()[0:1] and \
            (result.stdout or result.stderr).strip().splitlines()[0] or ""
    except (OSError, subprocess.SubprocessError) as exc:
        info["message"] = "dsh 存在但无法执行：%s" % exc

    home = os.environ.get("DSH_HOME") or os.path.join(os.path.expanduser("~"), ".dsh")
    profiles_dir = os.path.join(home, "profiles")
    try:
        info["profiles"] = sorted(
            name
            for name in os.listdir(profiles_dir)
            if os.path.isdir(os.path.join(profiles_dir, name))
            and not name.startswith(".")
            and name != "node_modules"
        )
        info["dsh_home"] = home
    except OSError:
        info["dsh_home"] = home
    return info


# --------------------------------------------------------------------------
# 框架元信息
# --------------------------------------------------------------------------


def _read_frontmatter_description(skill_path: str) -> str:
    try:
        with open(skill_path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return ""

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if match:
        block = match.group(1)
        desc = re.search(r"^description:\s*(.+?)\s*$", block, re.M)
        if desc:
            value = desc.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                return value

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---") or line.startswith("name:"):
            continue
        return line
    return ""


def _latest_mtime(root: str) -> float:
    latest = 0.0
    try:
        latest = os.path.getmtime(root)
    except OSError:
        return 0.0
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
        for name in files:
            try:
                latest = max(latest, os.path.getmtime(os.path.join(current, name)))
            except OSError:
                continue
    return latest


def frameworks_payload(config: dict) -> dict:
    items = []
    for item in FRAMEWORKS:
        skill_abs = os.path.join(REPO_ROOT, item["skill"])
        dir_abs = os.path.join(REPO_ROOT, item["dir"])
        mtime = _latest_mtime(dir_abs) if os.path.isdir(dir_abs) else 0.0
        items.append(
            {
                "key": item["key"],
                "name": item["name"],
                "dir": item["dir"],
                "skill": item["skill"],
                "summary": item["summary"],
                "skill_description": _read_frontmatter_description(skill_abs),
                "exists": os.path.isfile(skill_abs),
                "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "—",
                "modified_ts": mtime,
                "prompt": item["prompt"].format(skill=item["skill"]),
                "hint": item.get("hint", ""),
            }
        )
    return {"frameworks": items, "repo_root": REPO_ROOT, "dsh": dsh_info(config)}


# --------------------------------------------------------------------------
# 运行管理
# --------------------------------------------------------------------------


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RunManager:
    """管理 dsh one-shot 子进程：启动、流式收集输出、状态查询、落盘。"""

    def __init__(self, runs_dir: str):
        self.runs_dir = runs_dir
        self._lock = threading.Lock()
        self._runs = {}
        os.makedirs(self.runs_dir, exist_ok=True)
        self._load_history()

    # ---------------- 持久化 ----------------

    def _meta_path(self, run_id: str) -> str:
        return os.path.join(self.runs_dir, run_id + ".json")

    def _log_path(self, run_id: str) -> str:
        return os.path.join(self.runs_dir, run_id + ".log")

    def _save_meta(self, record: dict) -> None:
        payload = {key: value for key, value in record.items() if key != "output"}
        tmp = self._meta_path(record["id"]) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, self._meta_path(record["id"]))
        except OSError as exc:
            sys.stderr.write("[workbench] 无法写入运行记录: %s\n" % exc)

    def _load_history(self) -> None:
        try:
            names = sorted(os.listdir(self.runs_dir))
        except OSError:
            return
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.runs_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    record = json.load(handle)
            except (ValueError, OSError):
                continue
            if not isinstance(record, dict) or "id" not in record:
                continue
            record.setdefault("output", "")
            record.setdefault("error", "")
            if record.get("status") == "running":
                # 服务重启前遗留的进程已不可达，标记为中断。
                record["status"] = "failed"
                record["error"] = "服务重启，运行状态丢失。"
                record["ended_at"] = record.get("ended_at") or _now()
                record["exit_code"] = record.get("exit_code")
            # 输出正文从同名 .log 恢复，保证重启后仍能查看历史运行的完整输出。
            log_path = self._log_path(record["id"])
            if os.path.isfile(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                        record["output"] = handle.read()
                except OSError:
                    pass
            self._runs[record["id"]] = record

    def _prune(self) -> None:
        if len(self._runs) <= MAX_RUNS_KEPT:
            return
        ordered = sorted(self._runs.values(), key=lambda r: r.get("started_ts", 0))
        for record in ordered[: len(self._runs) - MAX_RUNS_KEPT]:
            if record.get("status") == "running":
                continue
            self._runs.pop(record["id"], None)

    # ---------------- 启动 ----------------

    def start(self, framework_key: str, prompt: str, config: dict) -> dict:
        framework = next((f for f in FRAMEWORKS if f["key"] == framework_key), None)
        if framework is None:
            raise ValueError("未知框架：%s" % framework_key)

        prompt = (prompt or "").strip() or framework["prompt"].format(skill=framework["skill"])
        dsh_cfg = config.get("dsh", {})
        command = (dsh_cfg.get("command") or DEFAULT_CONFIG["dsh"]["command"]).strip()
        profile = (dsh_cfg.get("profile") or "headless").strip()
        extra_args = dsh_cfg.get("extra_args") or []
        if not isinstance(extra_args, list):
            extra_args = []

        # 允许用环境变量覆盖，便于在受限环境里做端到端自检。
        env_override = os.environ.get("WORKBENCH_DSH_CMD", "").strip()
        if env_override:
            command = env_override

        resolved, problem = resolve_dsh(command)
        run_id = time.strftime("%Y%m%d-%H%M%S-") + framework_key
        suffix = 1
        with self._lock:
            while run_id in self._runs:
                suffix += 1
                run_id = time.strftime("%Y%m%d-%H%M%S-") + framework_key + "-%d" % suffix

        argv = [resolved or command, "--profile", profile, prompt] + [str(a) for a in extra_args]
        record = {
            "id": run_id,
            "framework": framework_key,
            "framework_name": framework["name"],
            "skill": framework["skill"],
            "prompt": prompt,
            "command": argv,
            "cwd": REPO_ROOT,
            "status": "running",
            "exit_code": None,
            "started_at": _now(),
            "started_ts": time.time(),
            "ended_at": None,
            "output": "",
            "error": "",
        }

        if resolved is None:
            record["status"] = "failed"
            record["exit_code"] = None
            record["ended_at"] = _now()
            record["error"] = (
                "启动失败：%s。请确认已安装 dsh（默认 /opt/homebrew/bin/dsh），"
                "或在“运行环境”里把命令改成真实可用的 dsh 路径。" % problem
            )
            with self._lock:
                self._runs[run_id] = record
            self._save_meta(record)
            return self._public(record, include_output=True)

        with self._lock:
            self._runs[run_id] = record
        self._save_meta(record)

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"

        # dsh 的 headless profile 从环境变量读取 provider 凭证
        # （缺失时报 MISSING_CREDENTIAL: llm-deepseek）。把工作台里配好的
        # DeepSeek 凭证透传给子进程，但绝不覆盖用户已有的环境变量。
        injected = []
        deepseek = config.get("deepseek", {})
        ds_key = (deepseek.get("api_key") or "").strip()
        if ds_key and not env.get("DEEPSEEK_API_KEY"):
            env["DEEPSEEK_API_KEY"] = ds_key
            injected.append("DEEPSEEK_API_KEY")
        ds_base = (deepseek.get("base_url") or "").strip()
        if ds_base and not env.get("DEEPSEEK_BASE_URL"):
            env["DEEPSEEK_BASE_URL"] = ds_base
            injected.append("DEEPSEEK_BASE_URL")
        record["env_injected"] = injected

        try:
            log_handle = open(self._log_path(run_id), "ab", buffering=0)
        except OSError:
            log_handle = None

        try:
            process = subprocess.Popen(
                argv,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
        except OSError as exc:
            if log_handle:
                log_handle.close()
            record["status"] = "failed"
            record["ended_at"] = _now()
            record["error"] = "启动子进程失败：%s" % exc
            self._save_meta(record)
            return self._public(record, include_output=True)

        record["pid"] = process.pid
        self._save_meta(record)

        worker = threading.Thread(
            target=self._consume, args=(run_id, process, log_handle), daemon=True
        )
        worker.start()
        return self._public(record, include_output=True)

    def _consume(self, run_id: str, process: subprocess.Popen, log_handle) -> None:
        record_ref = self._runs[run_id]
        injected = record_ref.get("env_injected") or []
        header = (
            "$ %s\n[cwd] %s\n[启动] %s\n[注入环境变量] %s\n%s\n"
            % (
                " ".join(_shell_quote(a) for a in record_ref["command"]),
                REPO_ROOT,
                record_ref["started_at"],
                "、".join(injected) if injected else "（无，沿用当前环境）",
                "-" * 60,
            )
        )
        self._append(run_id, header, log_handle)

        try:
            assert process.stdout is not None
            for line in process.stdout:
                self._append(run_id, line, log_handle)
        except Exception as exc:  # noqa: BLE001 - 读取异常也要落盘
            self._append(run_id, "\n[workbench] 读取子进程输出出错：%s\n" % exc, log_handle)
        finally:
            if process.stdout:
                try:
                    process.stdout.close()
                except OSError:
                    pass
            if log_handle:
                try:
                    log_handle.close()
                except OSError:
                    pass

        exit_code = process.wait()
        record = self._runs.get(run_id)
        if record is None:
            return
        record["exit_code"] = exit_code
        record["ended_at"] = _now()
        record["status"] = "succeeded" if exit_code == 0 else "failed"
        if exit_code != 0 and not record.get("error"):
            record["error"] = "dsh 退出码 %s，详见输出日志。" % exit_code

        # 收尾信息必须同时进内存和 .log，否则重启后恢复的输出会缺最后一行。
        trailer = "\n[workbench] 进程结束，退出码 %s\n" % exit_code
        try:
            with open(self._log_path(run_id), "ab", buffering=0) as tail:
                self._append(run_id, trailer, tail)
        except OSError:
            self._append(run_id, trailer, None)

        # 关键：把最终状态持久化，否则重启后历史记录会停留在 running。
        self._save_meta(record)

    def _append(self, run_id: str, text: str, log_handle) -> None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return
            record["output"] += text
        if log_handle:
            try:
                log_handle.write(text.encode("utf-8", "replace"))
            except (OSError, ValueError):
                pass

    # ---------------- 查询 ----------------

    def _public(self, record: dict, include_output: bool = False, offset: int = 0) -> dict:
        payload = {
            "id": record["id"],
            "framework": record.get("framework", ""),
            "framework_name": record.get("framework_name", ""),
            "skill": record.get("skill", ""),
            "prompt": record.get("prompt", ""),
            "command": record.get("command", []),
            "cwd": record.get("cwd", ""),
            "status": record.get("status", ""),
            "exit_code": record.get("exit_code"),
            "started_at": record.get("started_at", ""),
            "ended_at": record.get("ended_at"),
            "error": record.get("error", ""),
            "pid": record.get("pid"),
            "output_length": len(record.get("output", "")),
        }
        if include_output:
            output = record.get("output", "")
            offset = max(0, min(offset, len(output)))
            payload["output"] = output[offset:]
            payload["next_offset"] = len(output)
            payload["offset"] = offset
        return payload

    def get(self, run_id: str, offset: int = 0) -> dict:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return {}
            return self._public(record, include_output=True, offset=offset)

    def list(self, limit: int = 50) -> list:
        with self._lock:
            records = sorted(
                self._runs.values(), key=lambda r: r.get("started_ts", 0), reverse=True
            )
            return [self._public(record) for record in records[:limit]]


def _shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", value or ""):
        return value
    return "'" + (value or "").replace("'", "'\\''") + "'"


# --------------------------------------------------------------------------
# HTTP 路由
# --------------------------------------------------------------------------

RUN_MANAGER = RunManager(RUNS_DIR)


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = "HXWorkbench/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 工具方法 ----------

    def _send(self, status: int, body: bytes, content_type: str, extra_headers=None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _send_text(self, status: int, text: str) -> None:
        self._send(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def log_message(self, fmt, *args):  # noqa: A003 - 基类签名
        sys.stderr.write("[workbench] %s - %s\n" % (self.address_string(), fmt % args))

    # ---------- GET ----------

    def do_GET(self) -> None:  # noqa: N802 - 基类签名
        path = self.path.split("?", 1)[0]
        query = self.path.split("?", 1)[1] if "?" in self.path else ""

        if path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            full = os.path.join(WORKBENCH_DIR, filename)
            try:
                with open(full, "rb") as handle:
                    body = handle.read()
            except OSError:
                self._send_text(500, "缺少静态文件：%s" % filename)
                return
            self._send(200, body, content_type)
            return

        if path == "/api/frameworks":
            self._send_json(200, frameworks_payload(load_config()))
            return

        if path == "/api/config":
            self._send_json(200, public_config(load_config()))
            return

        if path == "/api/dsh":
            self._send_json(200, dsh_info(load_config()))
            return

        if path == "/api/wechat/status":
            # 只返回已记录的状态（不做网络调用，保持 GET 快速）。
            config = load_config()
            status = config.get("status", {})
            self._send_json(200, {
                "status": status.get("wechat", "待配置"),
                "status_message": status.get("wechat_message", ""),
                "credential_store": "macOS 钥匙串（service=%s）或环境变量" % WECHAT_KEYCHAIN_SERVICE,
                "check_script": WECHAT_API_SCRIPT_REL,
                "setup_script": WECHAT_SETUP_SCRIPT_REL,
            })
            return

        if path == "/api/runs":
            self._send_json(200, {"runs": RUN_MANAGER.list()})
            return

        if path.startswith("/api/runs/") or path.startswith("/api/run/"):
            run_id = path.rsplit("/", 1)[-1]
            offset = _parse_offset(query)
            record = RUN_MANAGER.get(run_id, offset=offset)
            if not record:
                self._send_json(404, {"error": "没有这条运行记录：%s" % run_id, "id": run_id})
                return
            self._send_json(200, record)
            return

        if path.startswith("/api/skill/"):
            self._serve_skill(path.rsplit("/", 1)[-1])
            return

        self._send_json(404, {"error": "未知路径：%s" % path})

    def _serve_skill(self, key: str) -> None:
        framework = next((f for f in FRAMEWORKS if f["key"] == key), None)
        if framework is None:
            self._send_json(404, {"error": "未知框架：%s" % key})
            return
        full = os.path.join(REPO_ROOT, framework["skill"])
        try:
            with open(full, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            self._send_text(404, "无法读取 %s：%s" % (framework["skill"], exc))
            return
        page = (
            "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>%s · SKILL.md</title><style>"
            "body{background:#0f1115;color:#e6e8ee;font:14px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;"
            "margin:0;padding:24px}h1{font-size:16px;color:#8ab4ff;font-weight:600}"
            "pre{white-space:pre-wrap;word-break:break-word;background:#161a22;border:1px solid #262c38;"
            "border-radius:10px;padding:18px}</style></head><body><h1>%s</h1><pre>%s</pre></body></html>"
            % (html.escape(framework["skill"]), html.escape(framework["skill"]), html.escape(text))
        )
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    # ---------- POST ----------

    def do_POST(self) -> None:  # noqa: N802 - 基类签名
        path = self.path.split("?", 1)[0]

        if path == "/api/config":
            apply_config_update(self._read_body())
            self._send_json(200, public_config(load_config()))
            return

        if path == "/api/test-deepseek":
            body = self._read_body()
            config = load_config()
            deepseek = dict(config.get("deepseek", {}))
            incoming = body.get("deepseek") if isinstance(body.get("deepseek"), dict) else body
            if isinstance(incoming, dict):
                key = (incoming.get("api_key") or "").strip()
                # 未改动的打码值 → 用已存的真实 key
                if key and not looks_masked(key):
                    deepseek["api_key"] = key
                if incoming.get("base_url"):
                    deepseek["base_url"] = incoming["base_url"].strip()
                if incoming.get("model"):
                    deepseek["model"] = incoming["model"].strip()

            result = test_deepseek(deepseek)
            config.setdefault("status", {})
            config["status"]["deepseek"] = "已连接" if result["ok"] else "连接失败"
            config["status"]["deepseek_message"] = result["message"]
            if result["ok"]:
                config["deepseek"]["base_url"] = deepseek.get("base_url", "")
                config["deepseek"]["model"] = deepseek.get("model", "")
            save_config(config)
            result["status"] = config["status"]["deepseek"]
            self._send_json(200, result)
            return

        if path == "/api/wechat/check":
            config = load_config()
            result = check_wechat_auth()
            refresh_wechat_status(config, result)
            self._send_json(200, result)
            return

        if path == "/api/wechat/configure":
            # 不在网页上收集密钥：只拉起仓库既成的交互式配置脚本。
            result = open_wechat_setup_terminal()
            self._send_json(200 if result["ok"] else 500, result)
            return

        if path == "/api/run":
            body = self._read_body()
            framework_key = body.get("framework") or body.get("key") or ""
            prompt = body.get("prompt") or ""
            try:
                record = RUN_MANAGER.start(framework_key, prompt, load_config())
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, record)
            return

        self._send_json(404, {"error": "未知路径：%s" % path})

    def do_HEAD(self) -> None:  # noqa: N802 - 基类签名
        self.do_GET()


def _parse_offset(query: str) -> int:
    for part in query.split("&"):
        if part.startswith("offset="):
            try:
                return max(0, int(part.split("=", 1)[1]))
            except ValueError:
                return 0
    return 0


# --------------------------------------------------------------------------
# 启动
# --------------------------------------------------------------------------


def pick_port(host: str, preferred: int) -> int:
    import socket

    for port in range(preferred, preferred + PORT_SCAN_LIMIT):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit("从 %d 开始的 %d 个端口都被占用，请用 --port 指定别的端口。" % (preferred, PORT_SCAN_LIMIT))


def main() -> int:
    parser = argparse.ArgumentParser(description="华鑫医药工作台本地服务")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="首选端口（默认 8765）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1，仅本机）")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--quiet-port-file", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    port = pick_port(args.host, args.port)
    os.makedirs(RUNS_DIR, exist_ok=True)

    server = ThreadingHTTPServer((args.host, port), WorkbenchHandler)
    server.daemon_threads = True
    url = "http://%s:%d/" % (args.host, port)

    try:
        with open(PORT_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(port))
    except OSError as exc:
        sys.stderr.write("[workbench] 无法写入端口文件：%s\n" % exc)

    if port != args.port:
        print("[workbench] 端口 %d 被占用，已自动顺延到 %d。" % (args.port, port))
    print("=" * 62)
    print("  华鑫医药工作台已启动")
    print("  地址: %s" % url)
    print("  仓库: %s" % REPO_ROOT)
    print("  停止: 在此终端按 Ctrl+C")
    print("=" * 62)
    sys.stdout.flush()

    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    # SIGTERM / SIGINT 都要走同一条收尾路径，否则会残留 runs/server.port。
    import signal

    def _graceful(signum, _frame):
        sys.stderr.write("\n[workbench] 收到信号 %s，正在停止…\n" % signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _graceful)
        except (ValueError, OSError):
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[workbench] 正在停止…")
    finally:
        server.shutdown()
        server.server_close()
        try:
            os.remove(PORT_FILE)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
