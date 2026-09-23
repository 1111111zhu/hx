#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核验周报 PNG 素材是否确实来自 Microsoft PowerPoint 幻灯片放映截图。

背景
----
用户反馈的实际缺陷：做周报公众号时直接拿 PPT 的预览画面（Preview / Quick Look /
Finder 预览 / 渲染导出）截图，而不是先打开 PowerPoint 进入幻灯片放映再截图。
规则文件里写了"必须从放映画面截图"，但没有可执行闸门。本脚本就是该闸门：
它把「放映截图」这一声明变成可核验的物理事实（文件指纹、页序、分辨率、比例、
重复页、来源不明的多余图片），退出码非 0 即不得交付。

用法
----
    python3 幻灯片截图核验.py \\
        --pptx        <源报告.pptx> \\
        --images      <截图目录> \\
        --manifest    <slideshow_capture.json> \\
        --expect-slides <报告页数> \\
        --json        <核验报告.json>

退出码
------
    0  全部通过
    1  核验失败（检测到非放映截图流程，或页序/尺寸/比例/重复页/多余图片等问题）
    2  参数或读取错误（路径不存在、manifest 不是合法 JSON、PPTX 无法解析等）

仅使用 Python 标准库（argparse/hashlib/json/re/struct/sys/zipfile/pathlib），
不联网，不依赖 Pillow。

截图过程记录 `slideshow_capture.json` 字段约定
---------------------------------------------
顶层字段：
    capture_method      str   必须为 "powerpoint_slideshow"；其它值（如
                              "preview_render"）判为「非放映截图流程」。
    application         str   必须包含 "PowerPoint"（大小写不敏感），
                              例如 "Microsoft PowerPoint"。
    slide_show_invoked  bool  必须为 true，表示确实进入了幻灯片放映。
    pptx_path           str   被截图的 PPTX 绝对路径（仅作提示与告警，不作硬校验）。
    pptx_sha256         str   该 PPTX 的 sha256，必须与 --pptx 实际文件一致。
    slide_count         int   该 PPTX 的幻灯片数，必须与 zip 内
                              ppt/slides/slide*.xml 的实际数量一致。
    captured_at         str   ISO-8601 时间戳，如 "2026-09-23T10:00:00+08:00"。
    display             obj   截取时显示器/放映画面参数：
        width_px        int   放映画面宽度（像素）
        height_px       int   放映画面高度（像素）
        scale           num   缩放倍率（信息字段，例如 2.0 表示 2x 屏）
    screenshots         list  逐张截图记录，每项：
        file            str   相对 --images 的文件名（可含子目录）
        kind            str   "report"（报告页）或 "compliance"（合规说明图）
        slide_index     int   报告页必须在 1..N 内，无缺无重；合规图可省略
        window_rect     obj   {"x","y","w","h"} 截图窗口/区域，仅信息与告警
        is_fullscreen   bool  true 表示全屏放映截图；为 true 时分辨率必须
                              与 display 完全一致

最小示例：
    {
      "capture_method": "powerpoint_slideshow",
      "application": "Microsoft PowerPoint",
      "slide_show_invoked": true,
      "pptx_path": "/abs/path/report.pptx",
      "pptx_sha256": "…",
      "slide_count": 12,
      "captured_at": "2026-09-23T10:00:00+08:00",
      "display": {"width_px": 2560, "height_px": 1440, "scale": 2.0},
      "screenshots": [
        {"file": "P01.png", "slide_index": 1, "kind": "report",
         "window_rect": {"x": 0, "y": 0, "w": 2560, "h": 1440},
         "is_fullscreen": true},
        {"file": "00_compliance.png", "kind": "compliance",
         "window_rect": {"x": 0, "y": 0, "w": 2560, "h": 1440},
         "is_fullscreen": true}
      ]
    }

核验项（逐条 PASS/FAIL 输出）
-----------------------------
    1   方法与身份          capture_method / application / slide_show_invoked
    2a  PPTX 指纹           manifest.pptx_sha256 == 实际文件 sha256
    2b  PPTX 页数           manifest.slide_count == zip 内 slide*.xml 数
    3a  报告页数量          report 条目数 == 幻灯片数或 --expect-slides
    3b  页序无重复          slide_index 不重复
    3c  页序完整            slide_index 恰为 1..N，无缺失、无越界
    3d  截图类型合法        kind 只能是 report / compliance，记录须为对象
    4a  截图文件存在        每条记录的文件存在，且同一文件不被重复引用
    4b  无来源不明 PNG      --images 内每个 PNG 都必须被 manifest 记录
    5a  PNG 可读            标准库解析 IHDR 取得宽高
    5b  尺寸匹配放映分辨率  报告页宽高 == display ±2 px
    5c  宽高比 16:9/16:10   容差 2%（排除带工具栏/缩略图窗格的窗口化截图）
    5d  全屏分辨率一致      is_fullscreen == true 时必须与 display 完全相等
    6   重复页检测          不同 slide_index 出现相同 sha256
    7   合规图处理          compliance 豁免 16:9 与页序，但仍须存在且不重复

已知能力边界（诚实说明）
------------------------
- 本脚本核验的是「记录与产物是否自洽、是否符合放映截图的物理特征」。它无法
  证明记录本身没有说谎：若把预览截图写进一份字段全部正确的放映记录，本脚本
  查不出来。因此规则同时要求记录必须反映真实的截图窗口。
- 报告页宽高按 --images 中图片与 manifest.display 的一致性判断；若实际流程
  裁掉了放映黑边导致尺寸变化，需要把 display 记为裁切后的画面尺寸，否则会
  在 5b/5d 失败。
- 合规说明图按模板内容区裁切，尺寸与比例本就不同于 16:9，因此 5b/5c/5d 不
  适用于 kind == "compliance"，其内容正确性由合规图上下留白检查另行负责。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ERROR = 2

CAPTURE_METHOD = "powerpoint_slideshow"
APPLICATION_TOKEN = "powerpoint"
KIND_REPORT = "report"
KIND_COMPLIANCE = "compliance"
ALLOWED_KINDS = (KIND_REPORT, KIND_COMPLIANCE)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DIMENSION_TOLERANCE_PX = 2
ASPECT_TOLERANCE = 0.02
TARGET_ASPECTS = (("16:9", 16.0 / 9.0), ("16:10", 16.0 / 10.0))

SLIDE_ENTRY_RE = re.compile(r"ppt/slides/slide(\d+)\.xml")

NON_FULLSCREEN_HINT = (
    "存在 is_fullscreen 非 true 的报告页记录（窗口化截图容易带入工具栏、"
    "缩略图窗格等界面元素）："
)


class InputError(Exception):
    """参数或读取错误，对应退出码 2。"""


class PngError(Exception):
    """PNG 头不可解析。"""


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def pptx_slide_count(path: Path) -> int:
    """用标准库 zipfile 统计 ppt/slides/slide*.xml，不依赖第三方库。"""
    with zipfile.ZipFile(path) as archive:
        names = {name for name in archive.namelist() if SLIDE_ENTRY_RE.fullmatch(name)}
    return len(names)


def read_png_size(path: Path) -> tuple:
    """只读 PNG 头，用 struct 解析 IHDR，取回 (width, height)。"""
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24:
        raise PngError("文件不足 24 字节，不是完整 PNG")
    if header[:8] != PNG_SIGNATURE:
        raise PngError("PNG 文件签名不匹配（可能是改名的 JPEG 或其它格式）")
    chunk_length = struct.unpack(">I", header[8:12])[0]
    chunk_type = header[12:16]
    if chunk_type != b"IHDR":
        raise PngError("首个数据块不是 IHDR")
    if chunk_length != 13:
        raise PngError("IHDR 长度异常（%d，应为 13）" % chunk_length)
    width, height = struct.unpack(">II", header[16:24])
    if width == 0 or height == 0:
        raise PngError("IHDR 宽或高为 0")
    return width, height


def aspect_label(width: int, height: int):
    """返回 (匹配的比例名 或 None, 实际比例)。"""
    ratio = width / height
    for label, target in TARGET_ASPECTS:
        if abs(ratio - target) / target <= ASPECT_TOLERANCE:
            return label, ratio
    return None, ratio


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_positive_int(value) -> bool:
    return is_int(value) and value > 0


def display_name(path: Path, base: Path) -> str:
    """优先显示相对截图目录的路径，便于同目录同名文件区分。"""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------- #
# 载入输入
# --------------------------------------------------------------------------- #
def load_manifest(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError("无法读取截图过程记录 %s：%s" % (path, exc))
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError("截图过程记录不是合法 JSON：%s" % exc)
    if not isinstance(payload, dict):
        raise InputError("截图过程记录顶层必须是 JSON 对象，实际是 %s" % type(payload).__name__)
    screenshots = payload.get("screenshots")
    if not isinstance(screenshots, list):
        raise InputError('截图过程记录缺少 screenshots 数组（字段约定见 --help 或脚本文档字符串）')
    return payload


def resolve_pptx(path: Path) -> int:
    if not path.is_file():
        raise InputError("源 PPTX 不存在或不是文件：%s" % path)
    try:
        count = pptx_slide_count(path)
    except zipfile.BadZipFile:
        raise InputError("源 PPTX 不是合法的 Office zip 包：%s" % path)
    except OSError as exc:
        raise InputError("无法读取源 PPTX %s：%s" % (path, exc))
    if count == 0:
        raise InputError("源 PPTX 中没有 ppt/slides/slide*.xml，幻灯片数为 0：%s" % path)
    return count


# --------------------------------------------------------------------------- #
# 核验
# --------------------------------------------------------------------------- #
class Verification:
    def __init__(self):
        self.checks = []
        self.warnings = []

    def add(self, check_id: str, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(
            {"id": check_id, "name": name, "ok": bool(ok), "detail": detail}
        )
        return bool(ok)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def failures(self):
        return [
            "%s %s：%s" % (item["id"], item["name"], item["detail"])
            for item in self.checks
            if not item["ok"]
        ]

    @property
    def ok(self) -> bool:
        return all(item["ok"] for item in self.checks)


def evaluate(pptx_path: Path, images_dir: Path, manifest: dict, manifest_path: Path,
             expect_slides) -> dict:
    verification = Verification()

    # ---------------- 事实采集 ---------------- #
    actual_sha = sha256_file(pptx_path)
    actual_slide_count = pptx_slide_count(pptx_path)

    method = manifest.get("capture_method")
    application = manifest.get("application")
    invoked = manifest.get("slide_show_invoked")
    manifest_sha = manifest.get("pptx_sha256")
    manifest_slide_count = manifest.get("slide_count")
    captured_at = manifest.get("captured_at")
    display = manifest.get("display")
    display_w = display.get("width_px") if isinstance(display, dict) else None
    display_h = display.get("height_px") if isinstance(display, dict) else None
    display_ok = is_positive_int(display_w) and is_positive_int(display_h)

    raw_entries = manifest.get("screenshots") or []
    malformed_entries = []
    entries = []
    for item in raw_entries:
        if not isinstance(item, dict):
            malformed_entries.append(item)
            continue
        kind_raw = item.get("kind")
        kind = kind_raw.strip().lower() if isinstance(kind_raw, str) else None
        entries.append(
            {
                "file": item.get("file"),
                "kind": kind,
                "kind_raw": kind_raw,
                "slide_index": item.get("slide_index"),
                "is_fullscreen": item.get("is_fullscreen"),
                "window_rect": item.get("window_rect"),
                "resolved": None,
                "attempted": "",
                "digest": None,
                "size": None,
                "png_error": None,
            }
        )

    report_entries = [entry for entry in entries if entry["kind"] == KIND_REPORT]
    compliance_entries = [entry for entry in entries if entry["kind"] == KIND_COMPLIANCE]
    unknown_entries = [
        entry for entry in entries
        if entry["kind"] not in ALLOWED_KINDS
    ]

    # 文件定位（支持相对路径、basename 回退）
    missing_files = []
    for entry in entries:
        value = entry["file"]
        if not isinstance(value, str) or not value.strip():
            entry["attempted"] = repr(value)
            missing_files.append(entry)
            continue
        candidate = Path(value)
        entry["attempted"] = value
        target = candidate if candidate.is_absolute() else images_dir / candidate
        target = target.expanduser()
        if target.is_file():
            entry["resolved"] = target.resolve()
            continue
        fallback = images_dir / candidate.name
        if fallback.is_file():
            entry["resolved"] = fallback.resolve()
            continue
        missing_files.append(entry)

    # 同一文件被多条记录引用
    by_path = {}
    for entry in entries:
        if entry["resolved"] is not None:
            by_path.setdefault(entry["resolved"], []).append(entry)
    duplicate_refs = {path: group for path, group in by_path.items() if len(group) > 1}

    # 目录内所有 PNG
    actual_pngs = {
        path.resolve()
        for path in images_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".png"
    }
    referenced = set(by_path)
    extra_pngs = sorted(actual_pngs - referenced)

    # 读取 PNG 尺寸与 sha256
    for entry in entries:
        if entry["resolved"] is None:
            continue
        try:
            entry["size"] = read_png_size(entry["resolved"])
        except PngError as exc:
            entry["png_error"] = str(exc)
        except OSError as exc:
            entry["png_error"] = "读取失败：%s" % exc
        else:
            entry["digest"] = sha256_file(entry["resolved"])

    # 覆盖完整性
    expected_report_count = expect_slides if expect_slides is not None else actual_slide_count
    index_values = [entry["slide_index"] for entry in report_entries]
    invalid_index_types = [value for value in index_values if not is_int(value)]
    good_indexes = [value for value in index_values if is_int(value)]
    seen = {}
    for value in good_indexes:
        seen[value] = seen.get(value, 0) + 1
    duplicate_indexes = sorted(value for value, count in seen.items() if count > 1)
    missing_indexes = sorted(set(range(1, expected_report_count + 1)) - set(seen))
    out_of_range = sorted(value for value in seen if value < 1 or value > expected_report_count)

    # 重复内容检测
    by_digest = {}
    for entry in entries:
        if entry["digest"]:
            by_digest.setdefault(entry["digest"], []).append(entry)
    duplicate_groups = [group for group in by_digest.values() if len(group) > 1]

    # ---------------- 逐项判定 ---------------- #
    # 1 方法与身份
    identity_problems = []
    if method != CAPTURE_METHOD:
        identity_problems.append(
            "capture_method=%r，应为 %r" % (method, CAPTURE_METHOD)
        )
    if not (isinstance(application, str) and APPLICATION_TOKEN in application.casefold()):
        identity_problems.append("application=%r，应包含 “PowerPoint”" % (application,))
    if invoked is not True:
        identity_problems.append("slide_show_invoked=%r，应为 true" % (invoked,))
    if identity_problems:
        verification.add(
            "1", "方法与身份", False,
            "检测到非放映截图流程：" + "；".join(identity_problems),
        )
    else:
        verification.add(
            "1", "方法与身份", True,
            "capture_method=%s，application=%r，slide_show_invoked=true"
            % (CAPTURE_METHOD, application),
        )

    # 2a PPTX 指纹
    sha_ok = isinstance(manifest_sha, str) and manifest_sha.strip().casefold() == actual_sha
    if sha_ok:
        verification.add("2a", "PPTX 指纹", True, "manifest.pptx_sha256 与源文件一致（%s…）" % actual_sha[:12])
    else:
        verification.add(
            "2a", "PPTX 指纹", False,
            "manifest.pptx_sha256=%r 与实际 sha256 %s 不一致：这批截图不是该 PPTX 的产物"
            % (manifest_sha, actual_sha),
        )

    # 2b PPTX 页数
    if is_int(manifest_slide_count) and manifest_slide_count == actual_slide_count:
        verification.add("2b", "PPTX 页数", True, "manifest 与源文件均为 %d 页" % actual_slide_count)
    else:
        verification.add(
            "2b", "PPTX 页数", False,
            "manifest.slide_count=%r，源 PPTX 实际 %d 页（按 ppt/slides/slide*.xml 计数）"
            % (manifest_slide_count, actual_slide_count),
        )

    # 3a 报告页数量
    if len(report_entries) == expected_report_count:
        source = "manifest.slide_count" if expect_slides is None else "--expect-slides"
        verification.add(
            "3a", "报告页数量", True,
            "report 条目 %d 条，与 %s（%d）一致" % (len(report_entries), source, expected_report_count),
        )
    else:
        verification.add(
            "3a", "报告页数量", False,
            "report 条目 %d 条，应为 %d 条（幻灯片数或 --expect-slides）；存在缺页或多余记录"
            % (len(report_entries), expected_report_count),
        )

    # 3b 页序无重复
    if duplicate_indexes or invalid_index_types:
        details = []
        if duplicate_indexes:
            details.append("重复的 slide_index：" + ",".join(str(v) for v in duplicate_indexes))
        if invalid_index_types:
            details.append("非整数的 slide_index：" + ", ".join(repr(v) for v in invalid_index_types))
        verification.add("3b", "页序无重复", False, "；".join(details))
    else:
        verification.add("3b", "页序无重复", True, "%d 个 slide_index 均唯一" % len(good_indexes))

    # 3c 页序完整
    if missing_indexes or out_of_range or invalid_index_types:
        details = []
        if missing_indexes:
            details.append("缺失页：" + ",".join(str(v) for v in missing_indexes))
        if out_of_range:
            details.append("越界页：" + ",".join(str(v) for v in out_of_range))
        if invalid_index_types:
            details.append("非整数的 slide_index：" + ", ".join(repr(v) for v in invalid_index_types))
        verification.add(
            "3c", "页序完整", False,
            "；".join(details) + "（应为 1..%d 且无缺失）" % expected_report_count,
        )
    else:
        verification.add("3c", "页序完整", True, "slide_index 恰为 1..%d，无缺失、无越界" % expected_report_count)

    # 3d 截图类型合法
    if unknown_entries or malformed_entries:
        details = []
        if unknown_entries:
            details.append(
                "未知的 kind：" + ", ".join(repr(entry["kind_raw"]) for entry in unknown_entries)
                + "（只能是 %s）" % " / ".join(ALLOWED_KINDS)
            )
        if malformed_entries:
            details.append("存在 %d 条非对象的 screenshots 记录" % len(malformed_entries))
        verification.add("3d", "截图类型合法", False, "；".join(details))
    else:
        verification.add(
            "3d", "截图类型合法", True,
            "全部记录 kind 合法（report %d 条，compliance %d 条）"
            % (len(report_entries), len(compliance_entries)),
        )

    # 4a 截图文件存在且唯一引用
    if missing_files or duplicate_refs:
        details = []
        if missing_files:
            details.append(
                "以下记录的文件在截图目录中不存在：" + ", ".join(entry["attempted"] for entry in missing_files)
            )
        if duplicate_refs:
            details.append(
                "同一文件被多条记录引用："
                + ", ".join(sorted(display_name(path, images_dir) for path in duplicate_refs))
            )
        verification.add("4a", "截图文件存在", False, "；".join(details))
    else:
        verification.add("4a", "截图文件存在", True, "%d 条记录均对应唯一存在的文件" % len(entries))

    # 4b 无来源不明 PNG
    if extra_pngs:
        verification.add(
            "4b", "无来源不明 PNG", False,
            "截图目录存在 %d 个未被 manifest 记录的 PNG，来源不明不可交付：%s"
            % (len(extra_pngs), ", ".join(display_name(path, images_dir) for path in extra_pngs)),
        )
    else:
        verification.add(
            "4b", "无来源不明 PNG", True,
            "截图目录内 %d 个 PNG 全部被 manifest 记录" % len(actual_pngs),
        )

    # 5a PNG 可读
    unreadable = [entry for entry in entries if entry["resolved"] is not None and entry["png_error"]]
    if unreadable:
        verification.add(
            "5a", "PNG 可读", False,
            "；".join("%s：%s" % (entry["attempted"], entry["png_error"]) for entry in unreadable),
        )
    else:
        verification.add("5a", "PNG 可读", True, "可解析的记录均通过 PNG 签名与 IHDR 校验")

    # 5b 尺寸匹配放映分辨率
    size_problems = []
    if report_entries and not display_ok:
        verification.add(
            "5b", "尺寸匹配放映分辨率", False,
            "manifest.display.width_px/height_px 缺失或非法，无法核验报告页几何（display=%r）" % (display,),
        )
    else:
        for entry in report_entries:
            if entry["size"] is None:
                continue
            width, height = entry["size"]
            if abs(width - display_w) > DIMENSION_TOLERANCE_PX or abs(height - display_h) > DIMENSION_TOLERANCE_PX:
                size_problems.append(
                    "%s %dx%d 与 display %dx%d 不符（±%d px）"
                    % (entry["attempted"], width, height, display_w, display_h, DIMENSION_TOLERANCE_PX)
                )
        if size_problems:
            verification.add("5b", "尺寸匹配放映分辨率", False, "；".join(size_problems))
        else:
            verification.add(
                "5b", "尺寸匹配放映分辨率", True,
                "报告页尺寸均与 display %dx%d 一致（±%d px）" % (display_w, display_h, DIMENSION_TOLERANCE_PX),
            )

    # 5c 宽高比
    aspect_problems = []
    for entry in report_entries:
        if entry["size"] is None:
            continue
        width, height = entry["size"]
        label, ratio = aspect_label(width, height)
        if label is None:
            aspect_problems.append(
                "%s %dx%d 比例 %.4f 既不是 16:9 也不是 16:10（容差 2%%）"
                % (entry["attempted"], width, height, ratio)
            )
    if aspect_problems:
        verification.add(
            "5c", "宽高比 16:9/16:10", False,
            "；".join(aspect_problems) + "：疑似窗口化预览截图（可能带入工具栏或缩略图窗格）",
        )
    else:
        verification.add("5c", "宽高比 16:9/16:10", True, "报告页宽高比均在 16:9 或 16:10 的 2% 容差内")

    # 5d 全屏分辨率一致
    fullscreen_problems = []
    non_fullscreen = []
    for entry in report_entries:
        if entry["is_fullscreen"] is True:
            if entry["size"] is None:
                continue
            width, height = entry["size"]
            if width != display_w or height != display_h:
                fullscreen_problems.append(
                    "%s 标记 is_fullscreen=true 但为 %dx%d，display 为 %dx%d"
                    % (entry["attempted"], width, height, display_w, display_h)
                )
        elif entry["is_fullscreen"] is not True:
            non_fullscreen.append(entry)
    if fullscreen_problems:
        verification.add("5d", "全屏分辨率一致", False, "；".join(fullscreen_problems))
    else:
        verification.add("5d", "全屏分辨率一致", True, "标记全屏的报告页分辨率与 display 完全相等")
    if non_fullscreen:
        verification.warn(
            NON_FULLSCREEN_HINT + ", ".join(entry["attempted"] for entry in non_fullscreen)
        )

    # 6 重复页检测
    if duplicate_groups:
        details = []
        for group in duplicate_groups:
            labels = []
            for entry in group:
                index = entry["slide_index"]
                labels.append(
                    "%s(kind=%s%s)"
                    % (
                        entry["attempted"],
                        entry["kind_raw"],
                        "" if index is None else ", slide_index=%s" % (index,),
                    )
                )
            report_indexes = {
                entry["slide_index"] for entry in group if entry["kind"] == KIND_REPORT
            }
            if len(report_indexes) > 1:
                reason = "不同页出现完全相同的图片内容，说明未真正翻页"
            elif any(entry["kind"] == KIND_COMPLIANCE for entry in group):
                reason = "合规图与其它截图内容相同"
            else:
                reason = "同一页被重复记录"
            details.append("%s（%s）" % (" + ".join(labels), reason))
        verification.add("6", "重复页检测", False, "；".join(details))
    else:
        verification.add("6", "重复页检测", True, "各记录文件内容互不相同，无重复页")

    # 7 合规图处理
    compliance_duplicate = [
        group for group in duplicate_groups
        if any(entry["kind"] == KIND_COMPLIANCE for entry in group)
    ]
    compliance_missing = [entry for entry in compliance_entries if entry["resolved"] is None]
    if compliance_missing or compliance_duplicate:
        details = []
        if compliance_missing:
            details.append("合规图文件缺失：" + ", ".join(entry["attempted"] for entry in compliance_missing))
        if compliance_duplicate:
            details.append("合规图内容与其它截图重复")
        verification.add("7", "合规图处理", False, "；".join(details))
    else:
        names = ", ".join(entry["attempted"] for entry in compliance_entries) or "无"
        verification.add(
            "7", "合规图处理", True,
            "compliance 条目 %d 条（%s）：豁免 16:9 与页序检查，文件存在且不重复"
            % (len(compliance_entries), names),
        )
    if not compliance_entries:
        verification.warn("manifest 未记录任何 kind=\"compliance\" 的合规说明图，请确认合规图另行核验")

    # 附加告警（不影响退出码）
    manifest_pptx_path = manifest.get("pptx_path")
    if isinstance(manifest_pptx_path, str) and manifest_pptx_path.strip():
        try:
            recorded = Path(manifest_pptx_path).expanduser().resolve()
        except OSError:
            recorded = None
        if recorded is not None and recorded != pptx_path:
            verification.warn(
                "manifest.pptx_path=%s 与 --pptx %s 不同（以 sha256 校验为准）"
                % (manifest_pptx_path, pptx_path)
            )
    else:
        verification.warn("manifest 未记录 pptx_path")

    if expect_slides is not None and expect_slides != actual_slide_count:
        verification.warn(
            "--expect-slides=%d 与源 PPTX 实际页数 %d 不同；已按 --expect-slides 核验页序"
            % (expect_slides, actual_slide_count)
        )

    if isinstance(captured_at, str) and captured_at.strip():
        try:
            datetime.fromisoformat(captured_at.strip().replace("Z", "+00:00"))
        except ValueError:
            verification.warn("manifest.captured_at 不是可解析的 ISO-8601 时间：%r" % captured_at)
    else:
        verification.warn("manifest 未记录 captured_at")

    if isinstance(display, dict) and "scale" in display and not isinstance(display.get("scale"), (int, float)):
        verification.warn("manifest.display.scale 不是数字：%r" % (display.get("scale"),))

    images_report = []
    for entry in entries:
        width, height = entry["size"] if entry["size"] else (None, None)
        images_report.append(
            {
                "file": entry["attempted"],
                "kind": entry["kind_raw"],
                "slide_index": entry["slide_index"],
                "width_px": width,
                "height_px": height,
                "sha256": entry["digest"],
                "is_fullscreen": entry["is_fullscreen"],
                "resolved_path": str(entry["resolved"]) if entry["resolved"] else None,
                "error": entry["png_error"],
            }
        )

    return {
        "status": "pass" if verification.ok else "fail",
        "pptx_path": str(pptx_path),
        "pptx_sha256": actual_sha,
        "pptx_slide_count": actual_slide_count,
        "images_dir": str(images_dir),
        "manifest_path": str(manifest_path),
        "manifest_slide_count": manifest_slide_count,
        "expected_report_count": expected_report_count,
        "actual_report_count": len(report_entries),
        "report_slide_indexes": good_indexes,
        "compliance_files": [entry["attempted"] for entry in compliance_entries],
        "capture": {
            "capture_method": method,
            "application": application,
            "slide_show_invoked": invoked,
            "captured_at": captured_at,
            "display": display,
        },
        "images": images_report,
        "checks": verification.checks,
        "failures": verification.failures,
        "warnings": verification.warnings,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def print_summary(result: dict) -> None:
    lines = []
    lines.append("=" * 72)
    lines.append("PowerPoint 幻灯片放映截图核验")
    lines.append("=" * 72)
    lines.append("源 PPTX     ：%s" % result["pptx_path"])
    lines.append("截图目录    ：%s" % result["images_dir"])
    lines.append("过程记录    ：%s" % result["manifest_path"])
    lines.append(
        "幻灯片数    ：源文件 %d 页 / manifest 记录 %s"
        % (result["pptx_slide_count"], result["manifest_slide_count"])
    )
    lines.append(
        "报告页数量  ：应为 %d 页 / manifest 记录 %d 页"
        % (result["expected_report_count"], result["actual_report_count"])
    )
    lines.append("-" * 72)
    for item in result["checks"]:
        tag = "PASS" if item["ok"] else "FAIL"
        detail = "：%s" % item["detail"] if item["detail"] else ""
        lines.append("[%s] %-4s %s%s" % (tag, item["id"], item["name"], detail))
    lines.append("-" * 72)
    if result["warnings"]:
        lines.append("告警（不影响退出码）：")
        for message in result["warnings"]:
            lines.append("  ! %s" % message)
    if result["failures"]:
        lines.append("失败原因：")
        for message in result["failures"]:
            lines.append("  x %s" % message)
        lines.append("结论：核验不通过（%d 项失败）——该批 PNG 不得交付。" % len(result["failures"]))
    else:
        lines.append("结论：核验通过——该批 PNG 与放映截图记录自洽，可进入交付流程。")
    lines.append("=" * 72)
    print("\n".join(lines))


def write_json_report(path: Path, result: dict, exit_code: int) -> None:
    payload = dict(result)
    payload["exit_code"] = exit_code
    try:
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise InputError("无法写入结构化报告 %s：%s" % (path, exc))


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="幻灯片截图核验.py",
        description=(
            "核验周报 PNG 素材是否确实来自 Microsoft PowerPoint 幻灯片放映截图，"
            "而不是 Preview / Quick Look / 渲染导出的预览截图。"
        ),
        epilog=(
            "截图过程记录字段约定见本脚本文档字符串（python3 -c \"import ...\" 或直接查看源码顶部）：\n"
            "  capture_method      \"powerpoint_slideshow\"\n"
            "  application         含 \"PowerPoint\"\n"
            "  slide_show_invoked  true\n"
            "  pptx_path / pptx_sha256 / slide_count / captured_at\n"
            "  display             {width_px, height_px, scale}\n"
            "  screenshots[]       {file, slide_index, kind(report|compliance), window_rect, is_fullscreen}\n"
            "退出码：0=通过，1=核验失败，2=参数或读取错误。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--pptx", required=True, help="源 PPTX 路径（必填）")
    parser.add_argument("--images", required=True, help="截图 PNG 所在目录（必填）")
    parser.add_argument(
        "--manifest", required=True,
        help="截图过程记录 JSON，例如 slideshow_capture.json（必填）",
    )
    parser.add_argument(
        "--expect-slides", type=int, default=None, metavar="N",
        help="期望的报告页数量（不含合规图）；提供时替代 PPTX 实际页数作为页序基准",
    )
    parser.add_argument("--json", dest="json_out", default=None, metavar="PATH",
                        help="可选：输出结构化核验报告 JSON")
    return parser


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.expect_slides is not None and args.expect_slides < 1:
            raise InputError("--expect-slides 必须是正整数，实际为 %d" % args.expect_slides)

        pptx_path = Path(args.pptx).expanduser()
        if not pptx_path.is_file():
            raise InputError("源 PPTX 不存在或不是文件：%s" % args.pptx)
        pptx_path = pptx_path.resolve()
        actual_slide_count = resolve_pptx(pptx_path)

        images_dir = Path(args.images).expanduser()
        if not images_dir.is_dir():
            raise InputError("截图目录不存在或不是目录：%s" % args.images)
        images_dir = images_dir.resolve()

        manifest_path = Path(args.manifest).expanduser()
        if not manifest_path.is_file():
            raise InputError("截图过程记录不存在或不是文件：%s" % args.manifest)
        manifest_path = manifest_path.resolve()
        manifest = load_manifest(manifest_path)

    except InputError as exc:
        print("参数或读取错误：%s" % exc, file=sys.stderr)
        print("（退出码 2；字段约定见 --help）", file=sys.stderr)
        return EXIT_ERROR

    result = evaluate(pptx_path, images_dir, manifest, manifest_path, args.expect_slides)
    # resolve_pptx 已确认页数，这里保持一致
    result["pptx_slide_count"] = actual_slide_count
    exit_code = EXIT_PASS if result["status"] == "pass" else EXIT_FAIL
    print_summary(result)

    if args.json_out:
        try:
            write_json_report(Path(args.json_out).expanduser(), result, exit_code)
        except InputError as exc:
            print("参数或读取错误：%s" % exc, file=sys.stderr)
            return EXIT_ERROR
        else:
            print("结构化报告已写入：%s" % Path(args.json_out).expanduser().resolve())

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
