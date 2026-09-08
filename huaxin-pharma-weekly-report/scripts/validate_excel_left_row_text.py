#!/usr/bin/env python3
"""Fail when an Excel left evidence crop does not contain the complete PPT row text."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return "".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON array, or object containing an items array")
    parser.add_argument("--output", help="Optional audit JSON path")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise SystemExit("input must contain at least one item")

    audit = []
    failures = 0
    for index, item in enumerate(items, start=1):
        expected_raw = str(item.get("ppt_row_text") or "")
        actual_raw = str(item.get("excel_left_ocr_text") or "")
        expected = normalize(expected_raw)
        actual = normalize(actual_raw)
        reasons = []
        if not expected:
            reasons.append("missing_ppt_row_text")
        if not actual:
            reasons.append("missing_excel_left_ocr_text")
        if ("…" in actual_raw or "..." in actual) and "…" not in expected_raw and "..." not in expected:
            reasons.append("unexpected_ellipsis")
        if expected and actual and expected != actual:
            reasons.append("normalized_text_mismatch")
        status = "pass" if not reasons else "fail"
        failures += status == "fail"
        audit.append(
            {
                "id": item.get("id", index),
                "status": status,
                "reasons": reasons,
                "ppt_row_text_normalized": expected,
                "excel_left_ocr_text_normalized": actual,
            }
        )

    result = {"status": "pass" if failures == 0 else "fail", "count": len(audit), "failures": failures, "items": audit}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
