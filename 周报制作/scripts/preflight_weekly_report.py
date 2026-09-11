#!/usr/bin/env python3
"""Validate one Huaxin weekly-report pair and write a shared run manifest."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET


REQUIRED_SHEETS = {"P22行业政策", "P23-24行业新闻", "P25-26公司公告"}


def weekly_window(anchor: date) -> tuple[date, date]:
    days_since_friday = (anchor.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    end = anchor - timedelta(days=days_since_friday)
    return end - timedelta(days=6), end


def ppt_slide_count(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return len([name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)])


def xlsx_sheet_names(path: Path) -> list[str]:
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    return [node.attrib["name"] for node in root.findall("main:sheets/main:sheet", namespace)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", required=True)
    parser.add_argument("--xlsx", required=True)
    parser.add_argument("--anchor-date", default=date.today().isoformat())
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    pptx = Path(args.pptx).expanduser().resolve()
    xlsx = Path(args.xlsx).expanduser().resolve()
    anchor = datetime.strptime(args.anchor_date, "%Y-%m-%d").date()
    start, end = weekly_window(anchor)
    errors: list[str] = []

    if not pptx.is_file() or pptx.suffix.lower() != ".pptx":
        errors.append("PPTX file is missing or not a .pptx file.")
        slide_count = 0
    else:
        slide_count = ppt_slide_count(pptx)
        if slide_count < 8:
            errors.append(f"PPTX has {slide_count} slides; at least 8 are required.")

    if not xlsx.is_file() or xlsx.suffix.lower() != ".xlsx":
        errors.append("XLSX file is missing or not an .xlsx file.")
        sheet_names: list[str] = []
    else:
        sheet_names = xlsx_sheet_names(xlsx)
        normalized_sheet_names = {name.strip() for name in sheet_names}
        missing = sorted(REQUIRED_SHEETS.difference(normalized_sheet_names))
        if missing:
            errors.append("Missing required worksheets: " + ", ".join(missing))

    manifest = {
        "status": "ready" if not errors else "invalid_input",
        "anchor_date": anchor.isoformat(),
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "pptx": str(pptx),
        "xlsx": str(xlsx),
        "ppt_slide_count": slide_count,
        "xlsx_sheets": sheet_names,
        "stages": {
            "step1_research": "pending",
            "step2_policy": "pending",
            "step3_news": "pending",
            "step4_announcements": "pending",
        },
        "errors": errors,
    }
    Path(args.output).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise SystemExit("; ".join(errors))


if __name__ == "__main__":
    main()
