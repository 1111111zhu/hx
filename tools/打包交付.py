#!/usr/bin/env python3
"""把整个仓库打成"解压即自启"的交付压缩包。

产出结构：

    hx-工作台/
      启动工作台.command      <- 解压后双击这个
      README.md
      workbench/
      周报制作/  周报公众号发布/  通用文章公众号发布/
      tools/

排除：`.git`、运行时产物（config.json / runs/）、`__pycache__`、`.DS_Store`、
以及 `*_修正版.skill` 这类被正式规则取代的重复包。

要点：zip 条目会带上 Unix 权限位，所以 `启动工作台.command` 解压后仍是可执行的；
脚本最后会真的解压到临时目录并断言这一点。

用法：

    python3 tools/打包交付.py                    # 输出到仓库上一级目录
    python3 tools/打包交付.py --out /path/to.zip
    python3 tools/打包交付.py --no-repack         # 不重新打包 .skill，直接用现有的
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOP = "hx-工作台"

EXCLUDE_DIR_NAMES = {".git", "__pycache__", ".venv", "node_modules", "runs", ".dsh-module-fallback"}
EXCLUDE_FILE_NAMES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def canonical_skill_packages() -> set[Path]:
    """从 tools/打包skill.py 读取"正规分发包"清单。

    交付包里只放这些包；其它任何 `.skill`（`*_修正版.skill`、备份、手工试打等）
    一律排除。按名字模式去猜中文后缀不可靠——实测 `周报制作_公司公告截图修正版.skill`
    里 `修正版` 前面并没有下划线，`*_修正版.skill` 根本匹配不上。
    """
    spec = importlib.util.spec_from_file_location("_pkgskill", REPO / "tools" / "打包skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {(REPO / out_rel).resolve() for _name, _src, out_rel, _top in module.PACKAGES}


def collect(extra_skip: set[Path]) -> list[Path]:
    canonical = canonical_skill_packages()
    files: list[Path] = []
    for path in sorted(REPO.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO)
        if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
            continue
        if path.name in EXCLUDE_FILE_NAMES or path.suffix in EXCLUDE_SUFFIXES:
            continue
        # 只发正规 .skill，排除游离/被取代的分发包
        if path.suffix == ".skill" and path.resolve() not in canonical:
            continue
        if path in extra_skip:
            continue
        files.append(path)
    return files


def build(out: Path, repack: bool) -> int:
    if repack:
        print("→ 重新打包 .skill 分发文件…")
        rc = subprocess.run([sys.executable, str(REPO / "tools" / "打包skill.py")], cwd=REPO).returncode
        if rc != 0:
            print("错误：.skill 重新打包失败，已中止（避免发出规则过期的分发包）。", file=sys.stderr)
            return 1

    # 运行时产物不进交付包：config.json 可能含 key，runs/ 是日志
    skip = {REPO / "workbench" / "config.json", REPO / "workbench" / "runs"}
    files = [f for f in collect(set()) if not any(f == s or s in f.parents for s in skip)]

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in files:
            zf.write(path, f"{TOP}/{path.relative_to(REPO).as_posix()}")

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"→ 已写出 {out} （{len(files)} 个文件，{size_mb:.1f} MB）")
    return 0


def verify(archive: Path) -> int:
    """解压到临时目录，验证可执行位与关键文件齐全。

    注意：Python 的 `ZipFile.extractall()` **不会**还原 Unix 权限位，
    所以可执行位必须读 zip 的 `external_attr`（这才是各解压器实际依据的元数据），
    并在系统 `unzip` 可用时再做一次真实解压交叉验证。
    """
    print("→ 解压复核…")
    rc = 0

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)

            # 1) 依据 zip 元数据判断解压器会给出的权限
            for rel in ("启动工作台.command", "workbench/启动工作台.command"):
                key = f"{TOP}/{rel}"
                try:
                    attr = zf.getinfo(key).external_attr
                except KeyError:
                    print(f"   ✗ 缺失: {rel}")
                    rc = 1
                    continue
                mode = (attr >> 16) & 0o7777
                x = bool(mode & 0o100)
                print(f"   {'✓' if x else '✗'} {rel}  zip 记录权限={mode:o} 可执行={x}")
                if not x:
                    rc = 1

        root = Path(tmp) / TOP
        for label, path in (("服务端", root / "workbench" / "server.py"),
                            ("顶层启动入口", root / "启动工作台.command"),
                            ("工作台启动入口", root / "workbench" / "启动工作台.command")):
            if not path.is_file():
                print(f"   ✗ {label} 缺失: {path.relative_to(root)}")
                rc = 1

        # 2) 交付包不得含运行时密钥/日志
        if (root / "workbench" / "config.json").exists():
            print("   ✗ 交付包含有 workbench/config.json（可能带运行时密钥）")
            rc = 1
        else:
            print("   ✓ 未包含 workbench/config.json（无运行时密钥）")

        if (root / "workbench" / "runs").exists():
            print("   ✗ 交付包含有 workbench/runs/ 运行日志")
            rc = 1
        else:
            print("   ✓ 未包含 workbench/runs/")

        for req in ["README.md", "周报制作/SKILL.md", "周报公众号发布/SKILL.md",
                    "通用文章公众号发布/SKILL.md", "tools/打包skill.py",
                    "周报制作/references/研究成果/研究成果规则.md",
                    "周报制作/scripts/通用/证据图片版式核验.py",
                    "周报公众号发布/scripts/幻灯片截图核验.py"]:
            ok = (root / req).exists()
            print(f"   {'✓' if ok else '✗'} {req}")
            if not ok:
                rc = 1

    # 3) 用系统 unzip 真实解压，确认可执行位确实落地（macOS Archive Utility 同源行为）
    if shutil.which("unzip"):
        with tempfile.TemporaryDirectory() as tmp2:
            done = subprocess.run(["unzip", "-q", str(archive), "-d", tmp2],
                                  capture_output=True, text=True)
            if done.returncode != 0:
                print(f"   ✗ 系统 unzip 解压失败：{done.stderr.strip()[:200]}")
                rc = 1
            else:
                for rel in ("启动工作台.command", "workbench/启动工作台.command"):
                    p = Path(tmp2) / TOP / rel
                    x = bool(p.stat().st_mode & stat.S_IXUSR) if p.is_file() else False
                    print(f"   {'✓' if x else '✗'} 系统 unzip 解压后 {rel} 可执行={x}")
                    if not x:
                        rc = 1
    else:
        print("   · 未找到系统 unzip，跳过真实解压交叉验证")

    print("→ 复核" + ("通过" if rc == 0 else "失败"))
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="打出自启交付压缩包")
    parser.add_argument("--out", help="输出 zip 路径（默认写到仓库上一级目录）")
    parser.add_argument("--no-repack", action="store_true", help="不重新打包 .skill")
    parser.add_argument("--no-verify", action="store_true", help="跳过解压复核")
    args = parser.parse_args()

    stamp = _dt.date.today().strftime("%Y%m%d")
    out = Path(args.out) if args.out else REPO.parent / f"hx-工作台-{stamp}.zip"

    if build(out, repack=not args.no_repack) != 0:
        return 1
    if not args.no_verify and verify(out) != 0:
        return 1

    print(f"\n交付包就绪：{out}")
    print(f"用法：解压后双击 {TOP}/启动工作台.command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
