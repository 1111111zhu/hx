#!/usr/bin/env python3
"""Minimal, draft-only WeChat Official Account API adapter.

This script intentionally has no publish or mass-send command.
Credentials are read from macOS Keychain or environment variables and are
never printed.
"""

from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import os
import platform
import re
import secrets
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.weixin.qq.com"
KEYCHAIN_SERVICE = "codex-wechat-article"

# 公众号 AppID 形如 wx 开头 + 16 位十六进制，共 18 位；AppSecret 为 32 位十六进制。
# 这两个约束用于在**写入前**挡住明显错误的输入：此前 configure 只检查非空，
# 结果钥匙串里被存进了 11 位的 "hubo…" 和 9 位的 "0727…" 这类占位串，
# 之后每次 check-auth 都只能拿到无从解释的 errcode 40013。
APPID_PATTERN = re.compile(r"^wx[0-9a-fA-F]{16}$")
APPSECRET_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def credential_format_problems(app_id: str, app_secret: str) -> list[str]:
    """返回人类可读的格式问题清单；空列表表示格式正常。"""
    problems: list[str] = []
    if not APPID_PATTERN.match(app_id or ""):
        problems.append(
            f"AppID 格式不对：应为 18 位、以 wx 开头（例如 wx0123456789abcdef），"
            f"当前是 {len(app_id or '')} 位、以 {((app_id or '')[:4] or '空')!r} 开头"
        )
    if not APPSECRET_PATTERN.match(app_secret or ""):
        problems.append(
            f"AppSecret 格式不对：应为 32 位十六进制字符，当前是 {len(app_secret or '')} 位"
        )
    return problems



def _keychain_get(account: str) -> str | None:
    if platform.system() != "Darwin":
        return None
    try:
        p = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else None


def _keychain_set(account: str, value: str) -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("macOS 钥匙串不可用，请使用环境变量配置凭证")
    p = subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", account, "-w", value],
        check=False,
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError("写入 macOS 钥匙串失败")


def credential(name: str) -> str:
    value = _keychain_get(name) or os.environ.get(name)
    if not value:
        raise RuntimeError(f"缺少 {name}。先运行 configure，或设置同名环境变量。")
    return value


def request_json(method: str, url: str, payload: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"微信 API 请求失败：{exc}") from exc
    if isinstance(data, dict) and data.get("errcode", 0) != 0:
        raise RuntimeError(f"微信 API 返回错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def access_token() -> str:
    query = urllib.parse.urlencode(
        {"grant_type": "client_credential", "appid": credential("WECHAT_OFFICIAL_APP_ID"), "secret": credential("WECHAT_OFFICIAL_APP_SECRET")}
    )
    result = request_json("GET", f"{API}/cgi-bin/token?{query}")
    token = result.get("access_token")
    if not token:
        raise RuntimeError("微信未返回 access_token")
    return token


def multipart_upload(url: str, path: Path, field: str = "media") -> dict:
    if not path.is_file():
        raise RuntimeError(f"文件不存在：{path}")
    boundary = "----CodexWechat" + secrets.token_hex(12)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body = head + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return request_json(
        "POST",
        url,
        body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def configure(_: argparse.Namespace) -> None:
    app_id = input("公众号 AppID（输入时不会上传到 GitHub）：").strip()
    app_secret = getpass.getpass("公众号 AppSecret：").strip()
    if not app_id or not app_secret:
        raise RuntimeError("AppID 和 AppSecret 都不能为空")

    problems = credential_format_problems(app_id, app_secret)
    if problems:
        raise RuntimeError(
            "凭证格式校验未通过，已拒绝写入钥匙串：\n  - "
            + "\n  - ".join(problems)
            + "\n请到公众号后台「设置与开发 → 基本配置」复制正确的 AppID 与 AppSecret 后重试。"
        )

    if platform.system() == "Darwin":
        _keychain_set("WECHAT_OFFICIAL_APP_ID", app_id)
        _keychain_set("WECHAT_OFFICIAL_APP_SECRET", app_secret)
        print("已写入 macOS 钥匙串，不会生成 .env 文件。")
    else:
        print("当前系统不是 macOS。请将凭证写入系统密钥管理器或仅在当前进程设置环境变量：")
        print("WECHAT_OFFICIAL_APP_ID=...")
        print("WECHAT_OFFICIAL_APP_SECRET=...")


def check_auth(_: argparse.Namespace) -> None:
    # 先做本地格式校验：钥匙串里若已存着占位串，直接说清楚问题，
    # 而不是把一个无从解释的 errcode 40013 抛给使用者。
    try:
        app_id = credential("WECHAT_OFFICIAL_APP_ID")
        app_secret = credential("WECHAT_OFFICIAL_APP_SECRET")
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc

    problems = credential_format_problems(app_id, app_secret)
    if problems:
        raise RuntimeError(
            "本机保存的公众号凭证格式不对，无法换取 access_token：\n  - "
            + "\n  - ".join(problems)
            + "\n请运行 `python3 scripts/wechat_draft_api.py configure` 重新录入正确凭证。"
        )

    token = access_token()
    print(json.dumps({"ok": True, "access_token_received": bool(token), "token_value": "[redacted]"}, ensure_ascii=False))


def upload_thumb(args: argparse.Namespace) -> None:
    token = access_token()
    result = multipart_upload(f"{API}/cgi-bin/material/add_material?access_token={urllib.parse.quote(token)}&type=thumb", Path(args.file))
    print(json.dumps({"media_id": result.get("media_id"), "name": Path(args.file).name}, ensure_ascii=False))


def upload_image(args: argparse.Namespace) -> None:
    token = access_token()
    result = multipart_upload(f"{API}/cgi-bin/media/uploadimg?access_token={urllib.parse.quote(token)}", Path(args.file))
    print(json.dumps({"url": result.get("url"), "name": Path(args.file).name}, ensure_ascii=False))


def create_draft(args: argparse.Namespace) -> None:
    token = access_token()
    content = Path(args.content).read_text(encoding="utf-8")
    article = {
        "title": args.title,
        "author": args.author or "",
        "digest": args.digest or "",
        "content": content,
        "content_source_url": args.source_url or "",
        "thumb_media_id": args.thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    body = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
    result = request_json(
        "POST",
        f"{API}/cgi-bin/draft/add?access_token={urllib.parse.quote(token)}",
        body,
        {"Content-Type": "application/json; charset=utf-8"},
    )
    print(json.dumps({"ok": True, "media_id": result.get("media_id")}, ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="微信公众平台草稿 API，明确不支持发布")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("configure", help="本机安全配置 AppID/AppSecret").set_defaults(func=configure)
    sub.add_parser("check-auth", help="只读验证 access_token").set_defaults(func=check_auth)
    s = sub.add_parser("upload-thumb", help="上传草稿封面图")
    s.add_argument("file")
    s.set_defaults(func=upload_thumb)
    s = sub.add_parser("upload-image", help="上传正文图片并返回 URL")
    s.add_argument("file")
    s.set_defaults(func=upload_image)
    s = sub.add_parser("create-draft", help="创建公众号草稿；不会发布")
    s.add_argument("--title", required=True)
    s.add_argument("--content", required=True, help="HTML 正文文件")
    s.add_argument("--thumb-media-id", required=True)
    s.add_argument("--author")
    s.add_argument("--digest")
    s.add_argument("--source-url")
    s.set_defaults(func=create_draft)
    return p


if __name__ == "__main__":
    try:
        args = parser().parse_args()
        args.func(args)
    except KeyboardInterrupt:
        sys.exit("已取消")
    except Exception as exc:
        sys.exit(str(exc))
