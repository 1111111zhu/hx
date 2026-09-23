#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XLSX 证据图片版式核验 —— 核查华鑫医药周报证据工作簿里图片对象的真实版式。

用途
----
周报交付物是 PPTX + XLSX 配对文件；XLSX 用来放证据截图：每个证据项左侧一张
PPT 行截图，右侧一张或多张来源截图。历史缺陷是"同一项的多张来源截图在 Excel 里
叠在一起/互相覆盖"。本脚本重开已保存的 .xlsx，取出每张图片对象的实际绝对矩形，
按证据项分组做几何核验，输出 JSON 报告并用退出码表达通过/失败。

用法
----
    python3 证据图片版式核验.py <xlsx路径> [--plan 页序清单.json] [--min-gap 12] [--json 报告.json]

    # 只查证据工作表，并落一份结构化报告
    python3 证据图片版式核验.py 华鑫医药周报底稿.xlsx \
        --sheet P23-24行业新闻 --sheet P25-26公司公告 \
        --plan source_image_plan.json --json layout_report.json

退出码
------
    0  全部通过
    1  存在失败项（相交/间距不足/顺序不一致/锚点越界 …）
    2  参数错误、文件缺失、openpyxl 不可用或工作簿无法读取

运行解释器（重要）
------------------
本脚本需要 openpyxl（实测 3.1.5）。请优先使用仓库配套的虚拟环境解释器：

    /Users/zhujiaying/Documents/Codex/.venv/bin/python3      # openpyxl 3.1.5

脚本会按顺序自动探测以下解释器是否可用（仅用于友好提示，不会自己切换进程）：
    1) hx/.venv/bin/python3         （仓库内虚拟环境，若存在）
    2) ../.venv/bin/python3         （仓库同级的 Codex/.venv，本机实测可用）
    3) 当前 python3                  （系统 python3.9 亦已装 openpyxl 3.1.5）
若当前解释器缺少 openpyxl，脚本以退出码 2 报错并打印上面建议的解释器路径，
不会静默降级成"只统计不做几何检查"。

已实测验证的换算关系（详见 --help 与 references/通用规则/证据图片版式核验.md）
--------------------------------------------------------------------------
* EMU：DrawingML 的 `<xdr:colOff>` / `<xdr:rowOff>` / `<xdr:ext cx cy>` 单位都是
  EMU，**1 px = 9525 EMU**（等价 1 inch = 914400 EMU）。实测 `ext cx="6858000"`
  对应 PNG 自然宽度 720 px，`6858000 / 9525 = 720`，分毫不差。
* 图片绝对矩形：
    OneCellAnchor  left/top = 锚点单元格左上角 + colOff/rowOff；宽高取 `ext`。
    TwoCellAnchor  left/top 同上；宽高 = `to` 位置 − `from` 位置。
    AbsoluteAnchor left/top 取 `pos`（EMU）；宽高取 `ext`。
* 列宽（近似）：显式列宽 w 按 `px = round(w*7 + 5)`（w >= 1）；w < 1 按
  `round(w*12)`；隐藏列记 0 px；未声明列用 sheetFormatPr 的 defaultColWidth
  （缺省回退 8.43 字符 ≈ 64 px）。这是近似值，报告里标为 approximate。
* 行高（精确）：pt 转 px 用 `px = pt * 96 / 72`（1 pt = 1.3333… px），隐藏行记 0 px；
  未声明行用 sheetFormatPr 的 defaultRowHeight（缺省回退 15 pt）。
* 已知 Excel 噪声：Excel 会写出 `colOff="-1"`、`rowOff="1"` 这样的 EMU 取整残差
  （实测 P25-26 公司公告里就有 colOff=-1）。因此锚点越界与最小间距检查都带
  `--px-tolerance`（默认 0.5 px）容差，避免近似误差造成误报。

覆盖范围与已知不确定项
----------------------
* openpyxl 会**丢弃** WMF/EMF 图片（警告 "wmf image format is not supported so the
  image is being dropped"）。实测某真实底稿 drawing1.xml 有 80 张 pic，openpyxl
  只给出 79 张。因此本脚本以**原始 drawing XML 为准**提取全部 pic（含 EMF/WMF），
  再用 openpyxl 的 `ws._images` 做逐张对账，把被丢弃的图片标为 `xml_only`
  并计入 `reconciliation` 段，确保相交检查不会漏图。
* openpyxl 读取 `<col min="1" max="6" .../>` 这种区间时**只登记到 min 那一列**
  （见 openpyxl/worksheet/_reader.py 的 parse_column_dimensions），所以在多列同宽
  的工作表上 `ws.column_dimensions` 不可靠。本脚本自行解析 sheet XML 的 `<cols>`。
* 证据项分组没有 plan 时按启发式推断（左列图片划分条带）；这是推断，不是权威映射，
  报告里给出 `grouping_method`，有 `--plan` 时优先用清单映射。
* 折叠分组中未被 openpyxl 列出的行按"可见"处理；这类行若被隐藏会低估/高估 Y 坐标。
* 相交判定默认 0 容差（`--overlap-tolerance-px 0`）。Excel 自身的 EMU 取整可能造出
  ≤0.5 px 的亚像素相交，这类情况仍会被判失败，如需放宽请显式加容差。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# 常量：已实测验证的换算关系
# ---------------------------------------------------------------------------
EMU_PER_PX = 9525           # 实测：ext cx=6858000 ↔ 720 px
PX_PER_PT = 96.0 / 72.0     # 实测：行高 pt → px，1 pt = 1.3333… px
DEFAULT_COL_WIDTH_CHARS = 8.43   # Excel 缺省列宽 ≈ 64 px
DEFAULT_ROW_HEIGHT_PT = 15.0

XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

CHECK_NAMES = (
    "no_intersect",     # 1. 同表任意两图不得相交（默认 0 容差）
    "min_gap",          # 2. 同一项纵向相邻两图可见间距 >= min_gap px
    "stack_order",      # 3. 同一项同侧图片 top 严格递增（纵向独立排列）
    "side_by_side",     # 3b. 同一项右侧图片不得并排
    "anchor_offsets",   # 5. 锚点 colOff/rowOff 必须落在所在单元格内
    "plan_order",       # 4. 实际 top 顺序必须与页序清单一致
    "uniqueness",       # 6. 同一项右侧重复插入同一文件（二进制 hash）
)


class Fatal(Exception):
    """参数/读取类错误，退出码 2。"""


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def col_width_to_px(width_chars: float) -> float:
    """列宽（字符）→ 像素，近似公式；报告里标注 approximate。"""
    if width_chars is None:
        width_chars = DEFAULT_COL_WIDTH_CHARS
    if width_chars <= 0:
        return 0.0
    if width_chars < 1:
        return float(round(width_chars * 12))
    return float(round(width_chars * 7 + 5))


def natural_size(data: bytes):
    """从图片二进制头部读自然像素尺寸；EMF/WMF 等返回 None。"""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            import struct

            w, h = struct.unpack(">II", data[16:24])
            return int(w), int(h)
        if data[:6] in (b"GIF87a", b"GIF89a"):
            import struct

            w, h = struct.unpack("<HH", data[6:10])
            return int(w), int(h)
        if data[:2] == b"BM":
            import struct

            w, h = struct.unpack("<ii", data[18:26])
            return int(abs(w)), int(abs(h))
        if data[:2] == b"\xff\xd8":  # JPEG
            import struct

            i = 2
            n = len(data)
            while i + 9 < n:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                    return int(w), int(h)
                i += 2 + seg_len
    except Exception:
        return None
    return None


def overlap_area(a, b):
    """两个 (left, top, width, height) 矩形的重叠面积与重叠宽高。"""
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ox = min(ax0 + aw, bx0 + bw) - max(ax0, bx0)
    oy = min(ay0 + ah, by0 + bh) - max(ay0, by0)
    if ox <= 0 or oy <= 0:
        return 0.0, 0.0, 0.0
    return ox * oy, ox, oy


def resolve_part(base_dir: str, target: str) -> str:
    """把 OPC 关系里的相对 Target 解析成 zip 内的绝对部件名。"""
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base_dir, target))


def r2(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def rect_json(rect) -> dict:
    left, top, width, height = rect
    return {
        "left": r2(left),
        "top": r2(top),
        "width": r2(width),
        "height": r2(height),
        "right": r2(left + width),
        "bottom": r2(top + height),
    }


# ---------------------------------------------------------------------------
# 工作簿结构：sheet XML 路径、关系、媒体
# ---------------------------------------------------------------------------
class Book:
    """原始 XLSX 包的只读视图：sheet XML、drawing XML、媒体二进制。"""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.zip = zipfile.ZipFile(path)
            self.zip.testzip()
        except Exception as exc:  # noqa: BLE001
            raise Fatal(f"无法作为 XLSX(OOXML) 读取：{path}（{exc}）") from exc
        self._media_cache: dict[str, bytes] = {}
        self._digest_cache: dict[str, str] = {}
        self.sheet_parts = self._map_sheet_parts()

    def read(self, name: str) -> bytes:
        return self.zip.read(name)

    def _map_sheet_parts(self) -> dict[str, str]:
        rels = ET.fromstring(self.read("xl/_rels/workbook.xml.rels"))
        rid2target = {r.get("Id"): r.get("Target") for r in rels}
        root = ET.fromstring(self.read("xl/workbook.xml"))
        out: dict[str, str] = {}
        sheets = root.find(X + "sheets")
        if sheets is None:
            return out
        for sh in sheets:
            rid = sh.get(R + "id")
            target = rid2target.get(rid)
            if target:
                out[sh.get("name")] = resolve_part("xl", target)
        return out

    def sheet_rels(self, sheet_part: str) -> dict[str, str]:
        rels_part = posixpath.join(posixpath.dirname(sheet_part), "_rels", posixpath.basename(sheet_part) + ".rels")
        if rels_part not in self.zip.namelist():
            return {}
        root = ET.fromstring(self.read(rels_part))
        return {r.get("Id"): r.get("Target") for r in root}

    def drawing_rels(self, drawing_part: str) -> dict[str, str]:
        rels_part = posixpath.join(
            posixpath.dirname(drawing_part), "_rels", posixpath.basename(drawing_part) + ".rels"
        )
        if rels_part not in self.zip.namelist():
            return {}
        root = ET.fromstring(self.read(rels_part))
        out = {}
        for r in root:
            rtype = r.get("Type", "")
            if rtype.endswith("/image"):
                out[r.get("Id")] = resolve_part(posixpath.dirname(drawing_part), r.get("Target"))
        return out

    def media_bytes(self, part: str) -> bytes:
        if part not in self._media_cache:
            try:
                self._media_cache[part] = self.read(part)
            except KeyError:
                self._media_cache[part] = b""
        return self._media_cache[part]

    def media_digest(self, part: str) -> str:
        if part not in self._digest_cache:
            self._digest_cache[part] = sha256_hex(self.media_bytes(part))
        return self._digest_cache[part]


# ---------------------------------------------------------------------------
# 网格换算：列宽/行高 → 像素前缀和
# ---------------------------------------------------------------------------
def parse_cols(sheet_xml: bytes) -> list[dict]:
    """自行解析 <cols>，因为 openpyxl 会把区间折叠到 min 列（见模块文档）。"""
    try:
        root = ET.fromstring(sheet_xml)
    except ET.ParseError:
        return []
    node = root.find(X + "cols")
    if node is None:
        return []
    out = []
    for c in node.findall(X + "col"):
        try:
            lo = int(c.get("min"))
            hi = int(c.get("max"))
        except (TypeError, ValueError):
            continue
        raw_width = c.get("width")
        out.append(
            {
                "min": lo,
                "max": hi,
                "width": float(raw_width) if raw_width is not None else None,
                "hidden": str(c.get("hidden", "0")).lower() in ("1", "true"),
                "customWidth": str(c.get("customWidth", "0")).lower() in ("1", "true"),
            }
        )
    return out


class Grid:
    """把 (col, row) + EMU 偏移换算成绝对像素坐标。"""

    def __init__(self, ws, cols: list[dict]):
        self.ws = ws
        self.cols = cols
        sf = ws.sheet_format
        dcw = getattr(sf, "defaultColWidth", None)
        drh = getattr(sf, "defaultRowHeight", None)
        self.default_col_width = float(dcw) if dcw else DEFAULT_COL_WIDTH_CHARS
        self.default_row_height = float(drh) if drh else DEFAULT_ROW_HEIGHT_PT
        self._spec_cache: dict[int, dict | None] = {}
        self._col_prefix = [0.0]  # _col_prefix[i] = 第 i 列（0-based）左边界像素
        self._row_prefix = [0.0]  # _row_prefix[i] = 第 i 行（0-based）顶部像素
        self._row_cache: dict[int, float] = {}

    # -- 列 --
    def _spec(self, col0: int):
        if col0 not in self._spec_cache:
            idx = col0 + 1
            found = None
            for s in self.cols:
                if s["min"] <= idx <= s["max"]:
                    found = s
                    break
            self._spec_cache[col0] = found
        return self._spec_cache[col0]

    def col_width(self, col0: int) -> float:
        s = self._spec(col0)
        if s is None:
            width, hidden = self.default_col_width, False
        else:
            width = s["width"] if s["width"] is not None else self.default_col_width
            hidden = s["hidden"]
        if hidden:
            return 0.0
        return col_width_to_px(width)

    def col_left(self, col0: int) -> float:
        while len(self._col_prefix) <= col0:
            i = len(self._col_prefix) - 1
            self._col_prefix.append(self._col_prefix[i] + self.col_width(i))
        return self._col_prefix[col0]

    # -- 行 --
    def row_height(self, row1: int) -> float:
        if row1 not in self._row_cache:
            rd = self.ws.row_dimensions.get(row1)
            height, hidden = self.default_row_height, False
            if rd is not None:
                hidden = bool(rd.hidden)
                if rd.height is not None:
                    try:
                        height = float(rd.height)
                    except (TypeError, ValueError):
                        pass
            self._row_cache[row1] = 0.0 if hidden else max(0.0, height) * PX_PER_PT
        return self._row_cache[row1]

    def row_top(self, row0: int) -> float:
        while len(self._row_prefix) <= row0:
            i = len(self._row_prefix) - 1
            self._row_prefix.append(self._row_prefix[i] + self.row_height(i + 1))
        return self._row_prefix[row0]

    def row_hidden(self, row1: int) -> bool:
        rd = self.ws.row_dimensions.get(row1)
        return bool(rd.hidden) if rd is not None else False

    def col_hidden(self, col0: int) -> bool:
        s = self._spec(col0)
        return bool(s["hidden"]) if s else False


# ---------------------------------------------------------------------------
# 图片提取：XML（权威，含 EMF/WMF）+ openpyxl（对账）
# ---------------------------------------------------------------------------
def _norm_kind(kind: str) -> str:
    """统一 XML 局部名（oneCellAnchor）与 openpyxl 类名（OneCellAnchor），用于对账匹配。"""
    k = (kind or "").lower()
    if k.startswith("onecell"):
        return "oneCellAnchor"
    if k.startswith("twocell"):
        return "twoCellAnchor"
    if k.startswith("absolute"):
        return "absoluteAnchor"
    return kind


def _marker_tuple(node):
    """<xdr:from>/<xdr:to> → (col, row, colOff, rowOff)。"""
    if node is None:
        return None

    def val(tag):
        el = node.find(XDR + tag)
        if el is None or el.text is None:
            return 0
        try:
            return int(el.text)
        except ValueError:
            return 0

    return (val("col"), val("row"), val("colOff"), val("rowOff"))


def _ext_tuple(node):
    """<xdr:ext cx cy> → (cx, cy)，单位 EMU。"""
    if node is None:
        return None
    cx = node.get("cx")
    cy = node.get("cy")
    if cx is None and cy is None:
        return None
    try:
        return (int(cx or 0), int(cy or 0))
    except ValueError:
        return None


def extract_xml_pics(book: Book, drawing_part: str) -> tuple[list[dict], int, int]:
    """按文档顺序提取 drawing 内所有 pic（含 openpyxl 会丢掉的 EMF/WMF）。

    返回 (pics, 锚点总数, 未落在直接锚点下的 pic 数)。
    """
    root = ET.fromstring(book.read(drawing_part))
    rels = book.drawing_rels(drawing_part)
    pics: list[dict] = []
    anchor_count = 0
    orphan = 0
    for anchor in root:
        local = anchor.tag.split("}")[-1]
        if not local.endswith("Anchor"):
            continue
        anchor_count += 1
        frm = _marker_tuple(anchor.find(XDR + "from"))
        to = _marker_tuple(anchor.find(XDR + "to"))
        ext = _ext_tuple(anchor.find(XDR + "ext"))
        pos_node = anchor.find(XDR + "pos")
        pos = None
        if pos_node is not None:
            try:
                pos = (int(pos_node.get("x", 0)), int(pos_node.get("y", 0)))
            except ValueError:
                pos = None
        inner = list(anchor.iter(XDR + "pic"))
        if not inner:
            continue
        if len(inner) > 1:
            orphan += len(inner) - 1  # 组合内多图：共用组锚点，几何为近似
        for pic in inner:
            blip = pic.find(".//" + A + "blip")
            embed = blip.get(R + "embed") if blip is not None else None
            c_nv = pic.find(XDR + "nvPicPr/" + XDR + "cNvPr")
            media = rels.get(embed) if embed else None
            pics.append(
                {
                    "kind": local,
                    "from": frm,
                    "to": to,
                    "ext": ext,
                    "pos": pos,
                    "embed": embed,
                    "media_part": media,
                    "shape_id": c_nv.get("id") if c_nv is not None else None,
                    "shape_name": c_nv.get("name") if c_nv is not None else None,
                    "group_shared_anchor": len(inner) > 1,
                }
            )
    return pics, anchor_count, orphan


def extract_openpyxl_pics(ws) -> list[dict]:
    out = []
    for img in getattr(ws, "_images", None) or []:
        anchor = img.anchor
        kind = type(anchor).__name__
        frm = getattr(anchor, "_from", None)
        if frm is None:
            frm = getattr(anchor, "from", None)
        to = getattr(anchor, "to", None)
        ext = getattr(anchor, "ext", None)

        def mt(m):
            if m is None:
                return None
            return (
                int(getattr(m, "col", 0) or 0),
                int(getattr(m, "row", 0) or 0),
                int(getattr(m, "colOff", 0) or 0),
                int(getattr(m, "rowOff", 0) or 0),
            )

        def et(e):
            if e is None:
                return None
            cx, cy = getattr(e, "cx", None), getattr(e, "cy", None)
            if cx is None and cy is None:
                return None
            return (int(cx or 0), int(cy or 0))

        fmt = (getattr(img, "format", None) or "").lower()
        wh = (getattr(img, "width", None), getattr(img, "height", None))
        out.append(
            {
                "kind": kind,
                "key": (_norm_kind(kind), mt(frm), mt(to), et(ext)),
                "natural": wh if all(isinstance(v, (int, float)) for v in wh) else None,
                "format": fmt,
            }
        )
    return out


def compute_rect(pic: dict, grid: Grid):
    kind = pic["kind"]
    frm = pic["from"] or (0, 0, 0, 0)
    left = grid.col_left(frm[0]) + frm[2] / EMU_PER_PX
    top = grid.row_top(frm[1]) + frm[3] / EMU_PER_PX
    if kind == "absoluteAnchor" and pic.get("pos"):
        left = pic["pos"][0] / EMU_PER_PX
        top = pic["pos"][1] / EMU_PER_PX
    width = height = 0.0
    if kind == "twoCellAnchor" and pic.get("to"):
        tc, tr, tco, tro = pic["to"]
        right = grid.col_left(tc) + tco / EMU_PER_PX
        bottom = grid.row_top(tr) + tro / EMU_PER_PX
        width, height = right - left, bottom - top
    elif pic.get("ext"):
        width, height = pic["ext"][0] / EMU_PER_PX, pic["ext"][1] / EMU_PER_PX
    return left, top, width, height


def collect_sheet_images(book: Book, ws, sheet_part: str, warnings: list[dict]) -> dict:
    """抽取一张工作表里的全部图片对象，附对账信息。"""
    drawing_target = None
    for rid, target in book.sheet_rels(sheet_part).items():
        if target.endswith(".xml") and "drawings/" in target:
            drawing_target = resolve_part(posixpath.dirname(sheet_part), target)
            break
    if drawing_target is None:
        drawing_target = None

    xml_pics: list[dict] = []
    anchor_count = orphan = 0
    if drawing_target and drawing_target in book.zip.namelist():
        xml_pics, anchor_count, orphan = extract_xml_pics(book, drawing_target)

    grid = Grid(ws, parse_cols(book.read(sheet_part)))
    ox_pics = extract_openpyxl_pics(ws)
    ox_by_key = {}
    for p in ox_pics:
        ox_by_key.setdefault(p["key"], []).append(p)

    prefix = f"[{ws.title}]"
    images = []
    matched_openpyxl = 0
    for n, pic in enumerate(xml_pics, start=1):
        key = (_norm_kind(pic["kind"]), pic["from"], pic["to"], pic["ext"])
        candidates = ox_by_key.get(key) or []
        ox = candidates.pop(0) if candidates else None
        if ox is not None:
            matched_openpyxl += 1

        media = pic.get("media_part")
        data = book.media_bytes(media) if media else b""
        digest = book.media_digest(media) if media else ""
        ext_name = posixpath.splitext(media)[1].lstrip(".").lower() if media else ""
        natural = natural_size(data) if data else None
        if ox is not None and ox.get("natural"):
            natural = ox["natural"]

        rect = compute_rect(pic, grid)
        frm = pic["from"] or (0, 0, 0, 0)
        width_px, height_px = grid.col_width(frm[0]), grid.row_height(frm[1] + 1)
        images.append(
            {
                "index": n,
                "sheet": ws.title,
                "uid": f"{ws.title}#{n:02d}",
                "anchor_kind": pic["kind"],
                "anchor": {
                    "col": frm[0],
                    "row": frm[1],
                    "colOff_emu": frm[2],
                    "rowOff_emu": frm[3],
                    "colOff_px": r2(frm[2] / EMU_PER_PX),
                    "rowOff_px": r2(frm[3] / EMU_PER_PX),
                    "cell_col_letter": _col_letter(frm[0]),
                    "cell_row_1based": frm[1] + 1,
                    "cell_width_px": r2(width_px),
                    "cell_height_px": r2(height_px),
                    "cell_hidden": bool(grid.col_hidden(frm[0]) or grid.row_hidden(frm[1] + 1)),
                },
                "rect": rect_json(rect),
                "rect_px": (rect[0], rect[1], rect[2], rect[3]),
                "format": (ox["format"] if ox and ox.get("format") else ext_name),
                "natural_px": {"width": natural[0], "height": natural[1]} if natural else None,
                "media_part": media,
                "sha256": digest,
                "sha256_12": digest[:12],
                "source": "both" if ox is not None else "xml_only",
                "shape_id": pic.get("shape_id"),
                "shape_name": pic.get("shape_name"),
                "group_shared_anchor": pic.get("group_shared_anchor", False),
            }
        )

    dropped = [i for i in images if i["source"] == "xml_only"]
    if dropped:
        fmts = sorted({(i["format"] or "?") for i in dropped})
        warnings.append(
            {
                "sheet": ws.title,
                "check": "completeness",
                "reason": "openpyxl 丢弃了不受支持的图片格式；已按 drawing XML 补全并纳入检查",
                "dropped_count": len(dropped),
                "formats": fmts,
                "dropped_indices": [i["index"] for i in dropped],
            }
        )
    if ox_pics and matched_openpyxl != len(ox_pics):
        warnings.append(
            {
                "sheet": ws.title,
                "check": "reconciliation",
                "reason": "openpyxl 图片数与 XML 匹配数不一致",
                "openpyxl_count": len(ox_pics),
                "matched": matched_openpyxl,
            }
        )
    if orphan:
        warnings.append(
            {
                "sheet": ws.title,
                "check": "completeness",
                "reason": "存在位于组合(group)内、共用组锚点的图片，其矩形为组锚点近似值",
                "count": orphan,
            }
        )

    return {
        "sheet": ws.title,
        "sheet_part": sheet_part,
        "drawing_part": drawing_target,
        "anchor_count": anchor_count,
        "xml_pic_count": len(xml_pics),
        "openpyxl_pic_count": len(ox_pics),
        "images": images,
        "grid": grid,
    }


def _col_letter(col0: int) -> str:
    letters = ""
    n = col0 + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


# ---------------------------------------------------------------------------
# 分组：证据项与"左/右"列簇
# ---------------------------------------------------------------------------
def x_clusters(images: list[dict], min_ratio: float = 0.5) -> list[list[int]]:
    """按 X 区间"显著重叠"把图片分成若干列簇，返回每个簇的图片下标列表。

    只有 X 重叠宽度 >= min_ratio * min(该图宽度, 簇的 X 并集宽度) 才算同一列。
    这样左右两栏若只擦边 10px（真实底稿中左图 720px 宽、右图起点 710px）不会被
    误并成一列，从而避免把"左↔右水平重叠"错报成"纵向间距不足"。
    规范的全部相交仍由 no_intersect 逐对判定，不依赖这里的分簇。
    """
    order = sorted(range(len(images)), key=lambda i: (images[i]["rect_px"][0], images[i]["rect_px"][1]))
    clusters: list[list[int]] = []
    cur: list[int] = []
    cur_left = cur_right = None
    for i in order:
        left, _, width, _ = images[i]["rect_px"]
        if cur:
            union_w = cur_right - cur_left
            ref = max(1.0, min(union_w, width))
            if cur_right - left < min_ratio * ref:
                clusters.append(cur)
                cur, cur_left, cur_right = [], None, None
        cur.append(i)
        cur_left = left if cur_left is None else min(cur_left, left)
        cur_right = left + width if cur_right is None else max(cur_right, left + width)
    if cur:
        clusters.append(cur)
    return clusters


def assign_items(images: list[dict], method_notes: list[str], plan_item_of: dict[int, str]) -> list[dict]:
    """把图片归到证据项，返回 item 列表。"""
    n = len(images)
    if n == 0:
        return []

    # 有 plan 的 hash 映射时直接采用清单的 item_id
    if plan_item_of and len(plan_item_of) == n:
        groups: dict[str, list[int]] = {}
        for i in range(n):
            groups.setdefault(plan_item_of[i], []).append(i)
        method_notes.append("plan_hash")
        return _finish_items(groups, images, "plan_hash")

    clusters = x_clusters(images)
    if len(clusters) >= 2:
        left_cluster = clusters[0]
        anchor_positions = sorted((images[i]["rect_px"][1], i) for i in left_cluster)
        bands = []
        for k, (top, idx) in enumerate(anchor_positions):
            nxt = anchor_positions[k + 1][0] if k + 1 < len(anchor_positions) else float("inf")
            bands.append({"top": top, "bottom": nxt, "left_idx": idx})
        groups = {f"item{k + 1}": [b["left_idx"]] for k, b in enumerate(bands)}
        unassigned = []
        for i in range(n):
            if any(i in v for v in groups.values()):
                continue
            top = images[i]["rect_px"][1]
            placed = False
            for k, b in enumerate(bands):
                if b["top"] - 1e-6 <= top < b["bottom"] - 1e-6:
                    groups.setdefault(f"item{k + 1}", []).append(i)
                    placed = True
                    break
            if not placed:
                unassigned.append(i)
        if unassigned:
            groups.setdefault("unassigned", []).extend(unassigned)
            method_notes.append("有图片落在所有左列条带之外 → 归入 unassigned")
        method_notes.append("按左列图片条带划分证据项（启发式）")
        return _finish_items(groups, images, "left_column_bands")

    # 只有一列时：按 Y 区间链接分组
    order = sorted(range(n), key=lambda i: (images[i]["rect_px"][1], images[i]["rect_px"][0]))
    groups = {}
    key = None
    cur_bottom = None
    for i in order:
        top, height = images[i]["rect_px"][1], images[i]["rect_px"][3]
        if key is None or top >= cur_bottom - 1e-9:
            key = f"item{len(groups) + 1}"
            groups[key] = []
            cur_bottom = top + height
        groups[key].append(i)
        cur_bottom = max(cur_bottom, top + height)
    method_notes.append("单列工作表 → 按 Y 区间链接分组（启发式）")
    return _finish_items(groups, images, "y_chain")


def _finish_items(groups: dict[str, list[int]], images: list[dict], method: str) -> list[dict]:
    items = []
    for key, idxs in groups.items():
        idxs = sorted(set(idxs), key=lambda i: (images[i]["rect_px"][1], images[i]["rect_px"][0]))
        sub = [images[i] for i in idxs]
        clusters = x_clusters(sub)
        # 列簇序号 0 = 最左（通常是 PPT 行截图）；其余为右侧来源截图。
        # 注意：x_clusters 返回的是 sub 内的局部下标，必须经 idxs 映射回 images 的全局下标。
        col_groups = []
        for c, cluster in enumerate(clusters):
            col_groups.append(
                {
                    "column_group": c,
                    "side": "left" if c == 0 and len(clusters) > 1 else ("single" if len(clusters) == 1 else "right"),
                    "indices": [idxs[j] for j in sorted(cluster, key=lambda j: sub[j]["rect_px"][1])],
                }
            )
        # 左↔右水平间隔（仅信息，用于人工比对交付规则里的 23±3 / 46±3 px 目标；
        # 负值等于相交，已由 no_intersect 判失败，这里不重复判失败）
        separation = None
        if len(col_groups) >= 2:
            lefts = [images[i] for i in col_groups[0]["indices"]]
            rights = [images[i] for i in col_groups[-1]["indices"]]
            if lefts and rights:
                l_right = max(im["rect_px"][0] + im["rect_px"][2] for im in lefts)
                r_left = min(im["rect_px"][0] for im in rights)
                separation = r_left - l_right
        items.append(
            {
                "item_id": key,
                "image_indices": idxs,
                "column_groups": col_groups,
                "grouping_method": method,
                "left_right_separation_px": r2(separation) if separation is not None else None,
            }
        )
    items.sort(key=lambda it: min((images[i]["rect_px"][1] for i in it["image_indices"]), default=0))
    for k, it in enumerate(items, start=1):
        it["ordinal"] = k
    return items


def plan_groups(entries: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for e in entries:
        groups.setdefault(e["item_id"], []).append(e)
    for item_id, rows in groups.items():
        rows.sort(key=lambda r: (r["sequence"] if r["sequence"] is not None else 10**9, r["_order"]))
    return groups


# ---------------------------------------------------------------------------
# 核验
# ---------------------------------------------------------------------------
def verify(options, sheet_data, plan_payload):
    min_gap = options.min_gap
    tol = options.px_tolerance
    ov_tol = options.overlap_tolerance_px
    enabled = set(options.checks)
    failures: list[dict] = []
    warnings: list[dict] = []

    def fail(check, **kw):
        failures.append({"check": check, **kw})

    for sd in sheet_data:
        sheet = sd["sheet"]
        images = sd["images"]
        notes: list[str] = []
        plan_item_of: dict[int, str] = {}

        # ---- plan 映射（按 hash 匹配图片二进制） ----
        plan_mode = None
        unmatched_plan_rows: list[dict] = []
        if plan_payload is not None:
            groups = plan_groups(plan_payload["entries"])
            hash_to_item: dict[str, str] = {}
            for item_id, rows in groups.items():
                for row in rows:
                    if row.get("sha256"):
                        hash_to_item[row["sha256"]] = item_id
            for i, img in enumerate(images):
                if img["sha256"] and img["sha256"] in hash_to_item:
                    plan_item_of[i] = hash_to_item[img["sha256"]]
            if plan_item_of:
                plan_mode = "hash"
                mapped_hashes = set()
                for item_id, rows in groups.items():
                    for row in rows:
                        if row.get("sha256"):
                            mapped_hashes.add(row["sha256"])
                for item_id, rows in groups.items():
                    for row in rows:
                        if not row.get("sha256"):
                            unmatched_plan_rows.append({"item_id": item_id, "image_path": row.get("image_path"),
                                                        "reason": "文件不可读或缺少 sha256"})
                del mapped_hashes
            else:
                plan_mode = "geometry"
                notes.append("plan 的 image_path 无法与工作簿内图片 hash 对应；改用条带位置近似映射")
                warnings.append(
                    {
                        "sheet": sheet,
                        "check": "plan_order",
                        "reason": "plan 无法按 hash 匹配到工作簿图片，顺序核验为近似模式",
                    }
                )

        items = assign_items(images, notes, plan_item_of)

        # ---- plan 顺序核验（按 hash 匹配到的图片） ----
        if plan_payload is not None and plan_mode == "hash" and "plan_order" in enabled:
            groups = plan_groups(plan_payload["entries"])
            for it in items:
                idxs = it["image_indices"]
                matched = [i for i in idxs if i in plan_item_of]
                item_ids = {plan_item_of[i] for i in matched}
                for item_id in item_ids:
                    rows = groups.get(item_id, [])
                    expected_hashes = [r["sha256"] for r in rows if r.get("sha256")]
                    actual = sorted((images[i] for i in matched if plan_item_of[i] == item_id),
                                    key=lambda im: (im["rect_px"][1], im["rect_px"][0]))
                    actual_hashes = [im["sha256"] for im in actual]
                    if len(actual_hashes) != len(expected_hashes):
                        warnings.append(
                            {
                                "sheet": sheet,
                                "check": "plan_order",
                                "item_id": item_id,
                                "reason": "清单张数与工作簿中该项匹配到的张数不一致",
                                "plan_count": len(expected_hashes),
                                "matched_count": len(actual_hashes),
                            }
                        )
                    if len(actual_hashes) >= 2 and actual_hashes != expected_hashes:
                        fail(
                            "plan_order",
                            sheet=sheet,
                            item_id=item_id,
                            reason="按 top 升序的实际顺序与页序清单不一致",
                            actual_image_indices=[im["index"] for im in actual],
                            actual_sha256_12=[h[:12] for h in actual_hashes],
                            expected_sha256_12=[h[:12] for h in expected_hashes],
                        )
                    it["plan_item_id"] = item_id

        # ---- 1. 同表任意两图不得相交 ----
        if "no_intersect" in enabled:
            for a in range(len(images)):
                for b in range(a + 1, len(images)):
                    area, ow, oh = overlap_area(images[a]["rect_px"], images[b]["rect_px"])
                    if area > ov_tol:
                        fail(
                            "no_intersect",
                            sheet=sheet,
                            image_index_a=images[a]["index"],
                            image_index_b=images[b]["index"],
                            overlap_area_px2=r2(area),
                            overlap_width_px=r2(ow),
                            overlap_height_px=r2(oh),
                            rect_a=images[a]["rect"],
                            rect_b=images[b]["rect"],
                            reason="两张图片矩形相交/覆盖",
                        )

        # ---- 每项：间距、纵向顺序、并排、唯一性 ----
        for it in items:
            it["failures"] = []
            it["warnings"] = []
            for cg in it["column_groups"]:
                idxs = [i for i in cg["indices"]]
                stacked = sorted((images[i] for i in idxs), key=lambda im: (im["rect_px"][1], im["rect_px"][0]))
                cg["image_indices"] = [im["index"] for im in stacked]
                for k in range(len(stacked) - 1):
                    prev, nxt = stacked[k], stacked[k + 1]
                    gap = nxt["rect_px"][1] - (prev["rect_px"][1] + prev["rect_px"][3])
                    pair = {
                        "sheet": sheet,
                        "item_id": it["item_id"],
                        "side": cg["side"],
                        "column_group": cg["column_group"],
                        "prev_index": prev["index"],
                        "next_index": nxt["index"],
                        "gap_px": r2(gap),
                        "required_gap_px": min_gap,
                        "tolerance_px": tol,
                    }
                    cg.setdefault("pairs", []).append(pair)
                    if "min_gap" in enabled and gap + tol < min_gap:
                        f = dict(pair, check="min_gap", reason="相邻两图可见垂直间距不足（或为负=重叠）")
                        fail(**f)
                        it["failures"].append(f)
                    if "stack_order" in enabled and nxt["rect_px"][1] <= prev["rect_px"][1]:
                        f = dict(pair, check="stack_order", reason="同一侧图片 top 未严格递增（疑似叠放）")
                        fail(**f)
                        it["failures"].append(f)

            # 3b 并排：同一项右侧若存在两个及以上列簇且 Y 相交 → 并排
            if "side_by_side" in enabled:
                non_left = [cg for cg in it["column_groups"] if cg["side"] != "left"]
                if len(non_left) >= 2:
                    for x in range(len(non_left)):
                        for y in range(x + 1, len(non_left)):
                            ia = [images[i] for i in non_left[x]["indices"]]
                            ib = [images[i] for i in non_left[y]["indices"]]
                            for pa in ia:
                                for pb in ib:
                                    area, _, _ = overlap_area(pa["rect_px"], pb["rect_px"])
                                    if area > ov_tol:
                                        f = {
                                            "check": "side_by_side",
                                            "sheet": sheet,
                                            "item_id": it["item_id"],
                                            "image_index_a": pa["index"],
                                            "image_index_b": pb["index"],
                                            "overlap_area_px2": r2(area),
                                            "reason": "同一项右侧图片并排（应改为严格自上而下）",
                                        }
                                        fail(**f)
                                        it["failures"].append(f)

            # 6. 同一项右侧重复插入同一文件
            if "uniqueness" in enabled:
                seen: dict[str, list[int]] = {}
                for cg in it["column_groups"]:
                    if cg["side"] == "left":
                        continue
                    for i in cg["indices"]:
                        if images[i]["sha256"]:
                            seen.setdefault(images[i]["sha256"], []).append(images[i]["index"])
                for digest, idxs in seen.items():
                    if len(idxs) > 1:
                        w = {
                            "check": "uniqueness",
                            "sheet": sheet,
                            "item_id": it["item_id"],
                            "sha256_12": digest[:12],
                            "image_indices": idxs,
                            "reason": "同一文件（相同二进制 hash）在同一项右侧出现多次",
                        }
                        warnings.append(w)
                        it["warnings"].append(w)

        # ---- 5. 锚点越界 ----
        if "anchor_offsets" in enabled:
            for pos, img in enumerate(images):
                a = img["anchor"]
                cw, ch = a["cell_width_px"], a["cell_height_px"]
                co, ro = a["colOff_px"], a["rowOff_px"]
                reasons = []
                if a["cell_hidden"]:
                    reasons.append("锚点所在行列被隐藏（单元格尺寸为 0 px，锚点无法归位）")
                if co < -tol:
                    reasons.append(f"colOff={co} px 为负")
                if ro < -tol:
                    reasons.append(f"rowOff={ro} px 为负")
                if ch <= 0 or ro > ch - 1e-9 + tol:
                    reasons.append(f"rowOff={ro} px 超出所在行高 {ch} px")
                if cw <= 0 or co > cw - 1e-9 + tol:
                    reasons.append(f"colOff={co} px 超出所在列宽 {cw} px")
                if reasons:
                    f = {
                        "check": "anchor_offsets",
                        "sheet": sheet,
                        "image_index": img["index"],
                        "item_id": _item_of(items, pos),
                        "cell": f"{a['cell_col_letter']}{a['cell_row_1based']}",
                        "colOff_px": co,
                        "rowOff_px": ro,
                        "cell_width_px": cw,
                        "cell_height_px": ch,
                        "reason": "；".join(reasons),
                    }
                    fail(**f)

        # ---- 附加（仅告警）：显示尺寸与自然像素宽高比不一致 ----
        for img in images:
            nat = img.get("natural_px")
            if not nat or not nat.get("width") or not nat.get("height"):
                continue
            _, _, w, h = img["rect_px"]
            if w <= 0 or h <= 0:
                continue
            disp = w / h
            natr = nat["width"] / nat["height"]
            if abs(disp - natr) / natr > 0.02:
                warnings.append(
                    {
                        "sheet": sheet,
                        "check": "aspect_ratio",
                        "image_index": img["index"],
                        "reason": "显示宽高比与图片自然宽高比不一致（可能被拉伸）",
                        "displayed_ratio": r2(disp, 4),
                        "natural_ratio": r2(natr, 4),
                    }
                )

        for pos, img in enumerate(images):
            img["item_id"] = _item_of(items, pos)
        sd["items"] = items
        sd["notes"] = notes
        sd["plan_mode"] = plan_mode
        sd["unmatched_plan_rows"] = unmatched_plan_rows

    return failures, warnings


def _item_of(items: list[dict], position: int) -> str | None:
    """按图片在 images 列表中的 0-based 位置查所属证据项。"""
    for it in items:
        if position in it["image_indices"]:
            return it.get("plan_item_id") or it["item_id"]
    return None


# ---------------------------------------------------------------------------
# plan 读取
# ---------------------------------------------------------------------------
def load_plan(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise Fatal(f"页序清单无法解析：{path}（{exc}）") from exc
    if isinstance(raw, dict):
        for key in ("items", "source_image_plan", "plan", "entries"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raise Fatal("页序清单 JSON 对象里找不到 items/source_image_plan 数组")
    if not isinstance(raw, list) or not raw:
        raise Fatal("页序清单必须是非空 JSON 数组")

    entries = []
    for order, row in enumerate(raw):
        if not isinstance(row, dict):
            raise Fatal(f"页序清单第 {order + 1} 行不是对象")
        item_id = row.get("item_id") or row.get("id") or row.get("item")
        image_path = row.get("image_path") or row.get("path") or row.get("source_path") or row.get("file")
        seq = row.get("sequence", row.get("seq", row.get("order")))
        if item_id is None or image_path is None:
            raise Fatal(f"页序清单第 {order + 1} 行缺少 item_id 或 image_path")
        try:
            seq = int(seq) if seq is not None else None
        except (TypeError, ValueError):
            seq = None
        digest = row.get("sha256")
        if not digest and image_path:
            p = Path(str(image_path)).expanduser()
            if not p.is_absolute():
                p = (path.parent / p).resolve()
            try:
                digest = sha256_hex(p.read_bytes())
            except Exception:  # noqa: BLE001
                digest = None
        entries.append(
            {
                "item_id": str(item_id),
                "sequence": seq,
                "image_path": str(image_path),
                "sha256": digest,
                "_order": order,
                "source_page": row.get("source_page"),
                "region_order": row.get("region_order"),
            }
        )
    return {"path": str(path), "entries": entries}


# ---------------------------------------------------------------------------
# 报告与输出
# ---------------------------------------------------------------------------
def build_report(args, plan_payload, sheet_data, failures, warnings) -> dict:
    sheets_out = []
    for sd in sheet_data:
        items_out = []
        for it in sd["items"]:
            items_out.append(
                {
                    "item_id": it.get("plan_item_id") or it["item_id"],
                    "inferred_item_id": it["item_id"],
                    "ordinal": it["ordinal"],
                    "grouping_method": it["grouping_method"],
                    "image_indices": [sd["images"][i]["index"] for i in it["image_indices"]],
                    "left_right_separation_px": it.get("left_right_separation_px"),
                    "column_groups": [
                        {
                            "column_group": cg["column_group"],
                            "side": cg["side"],
                            "image_indices": cg["image_indices"],
                            "pairs": [
                                {k: v for k, v in p.items() if k not in ("sheet", "item_id", "side", "column_group")}
                                for p in cg.get("pairs", [])
                            ],
                        }
                        for cg in it["column_groups"]
                    ],
                    "failures": it.get("failures", []),
                    "warnings": it.get("warnings", []),
                }
            )
        sheets_out.append(
            {
                "sheet": sd["sheet"],
                "sheet_part": sd["sheet_part"],
                "drawing_part": sd["drawing_part"],
                "anchor_count": sd["anchor_count"],
                "xml_pic_count": sd["xml_pic_count"],
                "openpyxl_pic_count": sd["openpyxl_pic_count"],
                "image_count": len(sd["images"]),
                "item_count": len(sd["items"]),
                "grouping_notes": sd["notes"],
                "plan_match_mode": sd["plan_mode"],
                "images": [{k: v for k, v in img.items() if k != "rect_px"} for img in sd["images"]],
                "items": items_out,
            }
        )
    total_images = sum(len(sd["images"]) for sd in sheet_data)
    total_items = sum(len(sd["items"]) for sd in sheet_data)
    return {
        "status": "fail" if failures else "pass",
        "xlsx": str(args.xlsx),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "interpreter": sys.executable,
        "openpyxl_version": _openpyxl_version(),
        "settings": {
            "min_gap_px": args.min_gap,
            "px_tolerance": args.px_tolerance,
            "overlap_tolerance_px": args.overlap_tolerance_px,
            "checks": list(args.checks),
            "sheets": args.sheet,
        },
        "units": {
            "emu_per_px": EMU_PER_PX,
            "px_per_pt": r2(PX_PER_PT, 6),
            "col_width_px_approx": "round(width*7+5) for width>=1; round(width*12) for width<1; hidden=0",
            "row_height_px_exact": "pt*96/72; hidden=0",
            "approx_fields": ["left", "top", "width", "height", "gap_px"],
            "note": "列宽为近似换算；行高为精确换算；间距检查带 px_tolerance 容差",
        },
        "plan": {
            "path": plan_payload["path"] if plan_payload else None,
            "entry_count": len(plan_payload["entries"]) if plan_payload else 0,
            "match_mode": sheet_data[0]["plan_mode"] if sheet_data else None,
        },
        "sheets": sheets_out,
        "failures": failures,
        "warnings": warnings,
        "summary": {
            "sheet_count": len(sheet_data),
            "image_count": total_images,
            "item_count": total_items,
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "failures_by_check": _tally(failures),
        },
    }


def _tally(items: list[dict]) -> dict:
    out: dict[str, int] = {}
    for it in items:
        out[it.get("check", "?")] = out.get(it.get("check", "?"), 0) + 1
    return out


def _openpyxl_version() -> str:
    try:
        import openpyxl

        return getattr(openpyxl, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        return "missing"


def print_summary(report: dict, args) -> None:
    print("=" * 78)
    print("XLSX 证据图片版式核验")
    print("=" * 78)
    print(f"文件      : {report['xlsx']}")
    print(f"解释器    : {report['interpreter']}  (openpyxl {report['openpyxl_version']})")
    print(f"换算      : 1 px = {EMU_PER_PX} EMU（精确）；行高 1 pt = {r2(PX_PER_PT, 4)} px（精确）；"
          f"列宽 ≈ round(width*7+5) px（近似）")
    print(f"参数      : min_gap={args.min_gap}px, 间距容差={args.px_tolerance}px, "
          f"相交容差={args.overlap_tolerance_px}px, checks={','.join(args.checks)}")
    if report["plan"]["path"]:
        print(f"页序清单  : {report['plan']['path']}（{report['plan']['entry_count']} 行, "
              f"匹配模式={report['plan']['match_mode']}）")
    print(f"总览      : 工作表 {report['summary']['sheet_count']} 个；"
          f"图片对象 {report['summary']['image_count']} 张；"
          f"证据项 {report['summary']['item_count']} 个")
    print()

    for sd in report["sheets"]:
        head = (f"[{sd['sheet']}] 图片 {sd['image_count']} 张"
                f"（XML pic {sd['xml_pic_count']} / openpyxl {sd['openpyxl_pic_count']}）"
                f"；证据项 {sd['item_count']} 个")
        print(head)
        if sd["grouping_notes"]:
            print("  分组方式: " + "；".join(sd["grouping_notes"]))
        for img in sd["images"]:
            rect = img["rect"]
            nat = img.get("natural_px")
            nat_s = f"{nat['width']}x{nat['height']}" if nat else "-"
            flag = "" if img["source"] == "both" else "  [openpyxl未解析]"
            print(
                f"  #{img['index']:02d} {img['anchor_kind'][:7]:7s} "
                f"x={rect['left']:.1f}..{rect['right']:.1f} "
                f"y={rect['top']:.1f}..{rect['bottom']:.1f} "
                f"({rect['width']:.1f}x{rect['height']:.1f}) "
                f"项={img['item_id']} 锚={img['anchor']['cell_col_letter']}{img['anchor']['cell_row_1based']}"
                f"+({img['anchor']['colOff_px']},{img['anchor']['rowOff_px']})px "
                f"自然={nat_s} hash={img['sha256_12']}{flag}"
            )
        for it in sd["items"]:
            if it.get("left_right_separation_px") is not None:
                print(f"  项 {it['item_id']} 左↔右水平间隔={it['left_right_separation_px']:.2f}px "
                      f"（信息项：交付规则目标 新闻 23±3 / 公司公告 46±3）")
            for cg in it["column_groups"]:
                for p in cg["pairs"]:
                    verdict = "OK" if p["gap_px"] + args.px_tolerance >= args.min_gap else "FAIL"
                    print(
                        f"  项 {it['item_id']} {cg['side']}(列簇{cg['column_group']}): "
                        f"#{p['prev_index']:02d}→#{p['next_index']:02d} 间距={p['gap_px']:.2f}px "
                        f"[{verdict}]"
                    )
        for f in [x for x in report["failures"] if x.get("sheet") == sd["sheet"]]:
            print(f"  失败[{f['check']}] {f.get('reason', '')} :: "
                  + json.dumps({k: v for k, v in f.items() if k not in ("check", "sheet", "reason")},
                               ensure_ascii=False))
        for w in [x for x in report["warnings"] if x.get("sheet") == sd["sheet"]]:
            print(f"  告警[{w['check']}] {w.get('reason', '')} :: "
                  + json.dumps({k: v for k, v in w.items() if k not in ("check", "sheet", "reason")},
                               ensure_ascii=False))
        print()

    s = report["summary"]
    print("-" * 78)
    if report["status"] == "pass":
        print(f"结果: 通过（failures=0, warnings={s['warning_count']}）")
    else:
        print(f"结果: 失败（failures={s['failure_count']}, warnings={s['warning_count']}）")
        print("失败分布: " + json.dumps(s["failures_by_check"], ensure_ascii=False))


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="证据图片版式核验.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "重开已保存的 .xlsx，取出每张图片对象的实际绝对矩形（left/top/width/height，像素），\n"
            "按证据项分组核验：不得相交、右侧纵向相邻间距 ≥ min-gap、纵向独立排列、\n"
            "页序与清单一致、锚点 colOff/rowOff 落在单元格内、同一项右侧不得重复插入同一文件。"
        ),
        epilog=(
            "示例:\n"
            "  证据图片版式核验.py 底稿.xlsx\n"
            "  证据图片版式核验.py 底稿.xlsx --plan source_image_plan.json --json layout.json\n"
            "  证据图片版式核验.py 底稿.xlsx --sheet P23-24行业新闻 --min-gap 12\n"
            "\n"
            "退出码: 0=通过, 1=有失败项, 2=参数/读取错误\n"
            "换算(已实测): 1 px = 9525 EMU；行高 pt*96/72（精确）；列宽 ≈ round(width*7+5) px（近似）\n"
            "运行解释器: 优先 /Users/zhujiaying/Documents/Codex/.venv/bin/python3（openpyxl 3.1.5）"
        ),
    )
    p.add_argument("xlsx", help="待核验的 .xlsx 路径")
    p.add_argument("--plan", help="可选页序清单 JSON：[{item_id, sequence, image_path}, ...]")
    p.add_argument("--min-gap", type=float, default=12.0, help="同一项纵向相邻两图的最小可见间距（px，默认 12）")
    p.add_argument("--json", dest="json_out", help="把结构化 JSON 报告写到该路径")
    p.add_argument("--sheet", action="append", default=None, help="只核验指定工作表（可重复；默认全部）")
    p.add_argument("--px-tolerance", type=float, default=0.5,
                   help="间距与锚点边界容差（px，默认 0.5，用于吸收列宽近似与 Excel EMU 取整残差）")
    p.add_argument("--overlap-tolerance-px", type=float, default=0.0,
                   help="相交判定容差（px，默认 0，即相交即失败）")
    p.add_argument("--checks", default=",".join(CHECK_NAMES),
                   help="启用哪些检查，逗号分隔（默认全部：" + ",".join(CHECK_NAMES) + "）")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.checks = [c.strip() for c in str(args.checks).split(",") if c.strip()]
    bad = [c for c in args.checks if c not in CHECK_NAMES]
    if bad:
        print(f"参数错误：未知检查项 {bad}；可用：{list(CHECK_NAMES)}", file=sys.stderr)
        return 2

    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("错误：当前解释器缺少 openpyxl。请改用：", file=sys.stderr)
        print("  /Users/zhujiaying/Documents/Codex/.venv/bin/python3 证据图片版式核验.py ...", file=sys.stderr)
        print("（或仓库内 hx/.venv/bin/python3）。本脚本不会降级为不做几何检查。", file=sys.stderr)
        return 2

    import warnings as _warnings

    _warnings.filterwarnings("ignore")  # 屏蔽 openpyxl 丢弃 emf/wmf 的告警，脚本自行补全

    xlsx = Path(args.xlsx).expanduser()
    if not xlsx.is_file():
        print(f"参数错误：找不到 xlsx 文件 {xlsx}", file=sys.stderr)
        return 2
    args.xlsx = xlsx.resolve()

    plan_payload = None
    if args.plan:
        try:
            plan_path = Path(args.plan).expanduser()
            if not plan_path.is_file():
                raise Fatal(f"找不到页序清单文件 {plan_path}")
            plan_payload = load_plan(plan_path)
        except Fatal as exc:
            print(f"参数错误：{exc}", file=sys.stderr)
            return 2

    try:
        book = Book(args.xlsx)
        wb = openpyxl.load_workbook(args.xlsx)
    except Fatal as exc:
        print(f"读取错误：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"读取错误：无法用 openpyxl 打开 {args.xlsx}（{exc}）", file=sys.stderr)
        return 2

    wanted = set(args.sheet) if args.sheet else None
    sheet_data = []
    warnings: list[dict] = []
    for ws in wb.worksheets:
        if wanted is not None and ws.title not in wanted:
            continue
        part = book.sheet_parts.get(ws.title)
        if part is None:
            warnings.append({"sheet": ws.title, "check": "read", "reason": "workbook.xml 中找不到该表的 XML 部件"})
            continue
        sheet_data.append(collect_sheet_images(book, ws, part, warnings))

    if wanted is not None:
        missing = sorted(wanted - {sd["sheet"] for sd in sheet_data})
        if missing:
            print(f"参数错误：工作簿中不存在工作表 {missing}", file=sys.stderr)
            return 2

    failures, warnings2 = verify(args, sheet_data, plan_payload)
    warnings.extend(warnings2)
    report = build_report(args, plan_payload, sheet_data, failures, warnings)

    print_summary(report, args)

    if args.json_out:
        out = Path(args.json_out).expanduser()
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"JSON 报告: {out.resolve()}")
        except Exception as exc:  # noqa: BLE001
            print(f"写入错误：无法写 JSON 报告 {out}（{exc}）", file=sys.stderr)
            return 2

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
