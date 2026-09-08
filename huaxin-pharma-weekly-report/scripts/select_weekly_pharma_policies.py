#!/usr/bin/env python3
"""Filter weekly official pharma-policy candidates without rewriting content."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y.%m.%d %H:%M",
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y.%m.%d %H:%M:%S",
)
TITLE_KEYS = ("title", "file_name", "name", "headline")
DATE_KEYS = ("published_at", "publish_date", "published", "date", "time")
URL_KEYS = ("url", "link", "href", "official_url", "source_url")
ISSUER_KEYS = ("issuer", "agency", "publisher", "department")
CONTENT_KEYS = ("core_content", "main_content", "summary", "content", "body")
SOURCE_KEYS = ("source", "source_name", "site")
SCORE_KEYS = ("impact_score", "score", "importance")

OFFICIAL_DOMAINS = (
    "nmpa.gov.cn", "cde.org.cn", "cmde.org.cn", "nhc.gov.cn",
    "ndcpa.gov.cn", "nhsa.gov.cn", "gov.cn", "natcm.gov.cn",
    "samr.gov.cn",
    # Official government mirrors used only when the central agency page is
    # protected from capture but the repost visibly cites the central source.
    "wsjkw.hebei.gov.cn", "wjw.shanxi.gov.cn", "wjw.xinjiang.gov.cn",
)
PHARMA_MARKERS = (
    "医药", "药品", "药物", "药械", "医疗器械", "医保", "医疗保障",
    "中药", "中医药", "临床试验", "审评审批", "注册", "基本药物",
    "合理用药", "药学", "处方", "集采", "价格", "基金监管",
    "诊疗方案", "生物制品", "细胞", "基因治疗", "CRO", "CDMO",
    "医疗", "卫生", "公共卫生", "疾病防控", "传染病", "防控方案",
    "疫苗", "接种", "服药",
)
EXCLUDE_MARKERS = (
    "招聘", "培训报名", "会议通知", "人事", "预算", "决算", "党建",
    "科普", "新闻发布会实录",
)
CONSULTATION_MARKERS = (
    "公开征求意见", "征求意见稿", "意见征集", "意见咨询", "咨询稿", "公开征集意见",
)
NORMATIVE_MARKERS = (
    "指南", "指导意见", "管理办法", "管理规定", "实施办法", "工作方案", "立项指南",
    "价格项目", "支付标准", "医保目录", "集中采购", "审评指导原则", "监管规则",
    "技术指导原则", "服务价格",
)
REGULATORY_FALLBACK_MARKERS = (
    "附条件批准", "批准上市", "获批上市", "创新药", "1类新药", "一类新药",
    "突破性治疗", "优先审评", "特别审批", "批准进口", "药品注册证书",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, action="append", help="JSON candidate export. Repeat as needed.")
    parser.add_argument("--anchor-date", help="YYYY-MM-DD; defaults to today.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--max-count", type=int, default=2, help="Maximum selected records; default 2 for the weekly report, 0 means all qualifying records.")
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results", "policies"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    raise ValueError(f"Unsupported input JSON shape: {path}")


def first_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def parse_datetime(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw)
    text = str(raw).strip().replace("T", " ").replace("Z", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    match = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day))
    return None


def active_cycle(anchor: date) -> tuple[datetime, datetime]:
    days_since_friday = (anchor.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    end_day = anchor - timedelta(days=days_since_friday)
    start_day = end_day - timedelta(days=6)
    return datetime.combine(start_day, time.min), datetime.combine(end_day, time.max)


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def is_official(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == domain or host.endswith("." + domain) for domain in OFFICIAL_DOMAINS)


def is_relevant(record: dict[str, Any], title: str, issuer: str, content: str) -> bool:
    category = str(record.get("category") or "")
    joined = f"{title} {issuer} {content} {category}"
    if any(marker in joined for marker in EXCLUDE_MARKERS):
        return False
    return any(marker.lower() in joined.lower() for marker in PHARMA_MARKERS)


def as_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def selection_tier(record: dict[str, Any], title: str, content: str) -> int | None:
    category = str(record.get("category") or "").lower()
    text = f"{title} {content} {category}".lower()
    if any(marker.lower() in text for marker in NORMATIVE_MARKERS):
        return 1
    if any(marker.lower() in text for marker in REGULATORY_FALLBACK_MARKERS):
        return 2
    return None


def heuristic_impact(title: str, content: str, tier: int) -> float:
    text = f"{title} {content}".lower()
    score = 100.0 if tier == 1 else 60.0
    weights = {
        "全国": 18, "医保": 18, "价格": 18, "支付": 16, "集采": 16,
        "规范整合": 12, "创新药": 16, "1类": 14, "附条件批准": 16,
        "首个": 14, "首次": 12, "重大": 10,
    }
    return score + sum(weight for marker, weight in weights.items() if marker.lower() in text)


def normalized_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    published = parse_datetime(first_value(raw, DATE_KEYS))
    title = str(first_value(raw, TITLE_KEYS) or "").strip()
    url = str(first_value(raw, URL_KEYS) or "").strip()
    issuer = str(first_value(raw, ISSUER_KEYS) or "").strip()
    content = str(first_value(raw, CONTENT_KEYS) or "").strip()
    if not all((published, title, url, issuer, content)) or not is_official(url):
        return None
    if any(marker in title or marker in content for marker in CONSULTATION_MARKERS):
        return None
    if not is_relevant(raw, title, issuer, content):
        return None
    tier = selection_tier(raw, title, content)
    if tier is None:
        return None
    supplied_score = as_number(first_value(raw, SCORE_KEYS))
    return {
        "published_at": published.isoformat(sep=" ", timespec="seconds"),
        "title": title,
        "issuer": issuer,
        "core_content": content,
        "url": url,
        "evidence_url": str(raw.get("evidence_url") or url).strip(),
        "source": str(first_value(raw, SOURCE_KEYS) or urlparse(url).netloc).strip(),
        "category": str(raw.get("category") or "").strip(),
        "selection_tier": tier,
        "impact_score": supplied_score or heuristic_impact(title, content, tier),
        "raw": raw,
    }


def main() -> None:
    args = parse_args()
    anchor = datetime.strptime(args.anchor_date, "%Y-%m-%d").date() if args.anchor_date else date.today()
    start, end = active_cycle(anchor)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for input_name in args.input:
        for raw in load_records(Path(input_name)):
            record = normalized_record(raw)
            if record is None:
                continue
            published = datetime.fromisoformat(record["published_at"])
            if not start <= published <= end:
                continue
            dedupe_key = normalize(record["url"]) or normalize(record["title"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            records.append(record)

    max_count = max(0, args.max_count)
    records.sort(
        key=lambda item: (
            item["selection_tier"],
            -item["impact_score"],
            -datetime.fromisoformat(item["published_at"]).timestamp(),
        )
    )
    if max_count:
        records = records[:max_count]
    records.sort(key=lambda item: (item["published_at"], item["impact_score"]), reverse=True)

    output = {
        "range_start": start.date().isoformat(),
        "range_end": end.date().isoformat(),
        "count": len(records),
        "required_count": max_count,
        "shortfall": max(0, max_count - len(records)) if max_count else 0,
        "fallback_used": any(item["selection_tier"] == 2 for item in records),
        "sources_used": sorted({item["source"] for item in records}),
        "items": records,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
