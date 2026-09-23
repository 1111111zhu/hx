#!/usr/bin/env python3
"""重新打包仓库内的 .skill 分发文件。

背景与动机：

1. 修改任何 skill 的规则后，如果不重新打包，`.skill` 分发文件里仍是旧规则。
2. 历史上 `周报制作.skill` 与 `周报公众号发布.skill` 的 zip 条目**没有设置 UTF-8 标志位**
   （flag_bits 的 0x800 位），中文顶层目录名在合规解压器里会变成 `σæ¿µèÑσê╢Σ╜£` 这类乱码。
   本脚本重新打包时由 Python 的 zipfile 自动写入 UTF-8 标志位，并在结束时断言校验。

用法：

    python3 tools/打包skill.py            # 重新打包全部
    python3 tools/打包skill.py --check    # 只校验现有包，不写文件
    python3 tools/打包skill.py 周报制作    # 只打包指定项
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (打包项名称, 源目录相对路径, 输出 .skill 相对路径, zip 内顶层目录名)
PACKAGES = [
    ("周报制作", "周报制作", "周报制作.skill", "周报制作"),
    ("周报公众号发布", "周报公众号发布", "周报公众号发布.skill", "周报公众号发布"),
    ("通用文章公众号发布", "通用文章公众号发布", "通用文章公众号发布.skill", "通用文章外发"),
    ("行业新闻专项包", "周报制作/行业新闻专项包", "周报制作/行业新闻专项包.skill", "huaxin-pharma-industry-news"),
]

# 打包时排除的文件/目录名
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".DS_Store", ".skill"}
EXCLUDE_NAMES = {".DS_Store"}


def included_files(root: Path) -> list[Path]:
    """收集要打包的文件。

    规则：一个 .skill 包内**不嵌套另一个 skill**。凡是子目录里自带 `SKILL.md` 的，
    整棵子树跳过（它会作为自己的 .skill 单独分发）。这既符合仓库原有约定，
    也避免把同一份 21MB 模板重复塞进两个包。
    """
    nested_skill_dirs: set[Path] = set()
    for skill_md in root.rglob("SKILL.md"):
        parent = skill_md.parent
        if parent != root:
            nested_skill_dirs.add(parent)

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if any(nested in path.parents for nested in nested_skill_dirs):
            continue
        if path.suffix in EXCLUDE_SUFFIXES or path.name in EXCLUDE_NAMES:
            continue
        files.append(path)
    return files


def needs_utf8_flag(name: str) -> bool:
    """只有非 ASCII 名字才需要 zip 的 UTF-8 标志位（bit 11）。

    纯 ASCII 名字不设该标志是符合 ZIP 规范的，不能算错。反过来，中文名若没设，
    解压器会按 cp437 解读，中文顶层目录名就会变成 `σæ¿µèÑσê╢Σ╜£` 这类乱码。
    """
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        return True
    return False


def build(name: str, src_rel: str, out_rel: str, top: str) -> int:
    src = REPO / src_rel
    out = REPO / out_rel
    if not src.is_dir():
        print(f"[跳过] {name}: 源目录不存在 {src_rel}")
        return 1

    files = included_files(src)
    if not files:
        print(f"[跳过] {name}: 源目录没有可打包文件")
        return 1

    # 先写临时文件，成功后再替换，避免半成品覆盖好包
    tmp = out.with_suffix(out.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            arcname = f"{top}/{path.relative_to(src).as_posix()}"
            zf.write(path, arcname)

    # 校验 UTF-8 标志位：含非 ASCII 的条目必须置位，否则解压出来是乱码
    with zipfile.ZipFile(tmp) as zf:
        bad = [i.filename for i in zf.infolist()
               if needs_utf8_flag(i.filename) and not (i.flag_bits & 0x800)]
        if bad:
            tmp.unlink(missing_ok=True)
            print(f"[失败] {name}: {len(bad)} 个中文条目缺少 UTF-8 标志位，例如 {bad[0]!r}")
            return 1

    tmp.replace(out)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"[完成] {name}: {len(files)} 个文件 -> {out_rel} ({size_mb:.1f} MB, 顶层目录 {top}/)")
    return 0


def check() -> int:
    rc = 0
    for name, _src, out_rel, top in PACKAGES:
        out = REPO / out_rel
        if not out.is_file():
            print(f"[缺失] {name}: {out_rel}")
            rc = 1
            continue
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            bad = [i.filename for i in zf.infolist()
                   if needs_utf8_flag(i.filename) and not (i.flag_bits & 0x800)]
        tops = sorted({n.split("/")[0] for n in names})
        status = "OK" if not bad and tops == [top] else "异常"
        print(f"[{status}] {name}: 顶层目录 {tops}, {len(names)} 个条目, 中文名缺 UTF-8 标志位 {len(bad)} 个")
        if bad or tops != [top]:
            rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="重新打包仓库内的 .skill 分发文件")
    parser.add_argument("names", nargs="*", help="只打包指定项（默认全部）")
    parser.add_argument("--check", action="store_true", help="只校验现有 .skill，不写文件")
    args = parser.parse_args()

    if args.check:
        return check()

    selected = [p for p in PACKAGES if not args.names or p[0] in args.names]
    if not selected:
        print(f"没有匹配的打包项。可选：{[p[0] for p in PACKAGES]}", file=sys.stderr)
        return 2

    rc = 0
    for package in selected:
        if build(*package) != 0:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
