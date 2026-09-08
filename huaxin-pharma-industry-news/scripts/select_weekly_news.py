#!/usr/bin/env python3
"""Select weekly 医药魔方Info news without engagement metrics."""

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
TITLE_KEYS = ("title", "headline", "name")
DATE_KEYS = ("published_at", "publish_time", "published", "publishedAt", "date", "time")
URL_KEYS = ("url", "link", "href", "article_url", "articleUrl", "source_url", "sourceUrl")
CONTENT_KEYS = (
    "first_paragraph_raw", "canonical_text", "source_content", "exact_excerpt",
    "content", "body", "article_text", "excerpt",
)
SOURCE_KEYS = ("source", "source_name", "sourceName", "publisher", "media")
CAPTURE_TIME_KEYS = ("captured_at", "capture_time", "source_capture_time")
SOURCE_EVIDENCE_KEYS = ("source_screenshot", "evidence_path", "screenshot", "source_crop")
DIRECT_PROMOTION_SIGNALS = (
    "邀请函", "会议报名", "活动报名", "免费报名", "扫码报名", "点击报名", "报名通道",
    "诚邀", "参会指南", "门票", "购票", "售票", "票务", "招商", "招展", "赞助招募",
    "活动预告", "直播预告", "直播预约", "开播预告", "会议预告", "大会预告", "倒计时",
)
TITLE_PROMOTION_SIGNALS = (
    "邀请函", "诚邀", "报名", "议程", "日程", "门票", "购票", "招商", "招展",
    "赞助", "直播预告", "直播预约", "开播预告", "倒计时", "培训班", "训练营",
    "招聘", "招募", "广告",
)
EVENT_SIGNALS = ("大会", "峰会", "论坛", "会议", "展会", "沙龙", "训练营", "闭门会", "路演")
PROMOTION_SIGNALS = (
    "报名", "扫码", "启幕", "开幕", "日程", "议程", "嘉宾", "门票", "购票", "参会",
    "招商", "招展", "赞助", "直播", "预约", "倒计时", "即将", "举办", "齐聚", "重磅来袭",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, action="append", help="医药魔方Info JSON export. Repeat only for 医药魔方Info exports.")
    parser.add_argument("--anchor-date", help="Anchor date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--count", type=int, default=10, help="Number of items to keep.")
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results", "news"):
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
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", text)
    if match:
        year, month, day, hour, minute, second = match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
    return None


def current_cycle(anchor: date) -> tuple[datetime, datetime]:
    # Use the most recently completed Friday, never the current incomplete
    # Friday/Saturday-through-Friday cycle.
    days_since_friday = (anchor.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    end_day = anchor - timedelta(days=days_since_friday)
    start_day = end_day - timedelta(days=6)
    return datetime.combine(start_day, time.min), datetime.combine(end_day, time.max)


def source_name(record: dict[str, Any], input_path: Path) -> str:
    source = str(first_value(record, SOURCE_KEYS) or "").strip()
    if source:
        return source
    if any(token in input_path.stem.lower() for token in ("pharmcube_info", "medalpha_info", "医药魔方info")):
        return "医药魔方Info"
    return ""


def is_medalpha(source: str, input_path: Path) -> bool:
    del input_path
    return source.strip().lower() == "医药魔方info".lower()


def is_info_wechat_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "mp.weixin.qq.com"
        and (parsed.path == "/s" or parsed.path.startswith("/s/"))
    )


def nested_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    value = first_value(record, keys)
    if value not in (None, ""):
        return value
    for container_key in ("evidence", "audit", "source"):
        container = record.get(container_key)
        if isinstance(container, dict):
            value = first_value(container, keys)
            if value not in (None, ""):
                return value
    return None


def is_invitation_or_event_promotion(title: str, source_content: str) -> bool:
    title_text = normalize(title)
    lead_text = normalize(source_content[:1200])
    combined = title_text + lead_text
    if any(signal in title_text for signal in TITLE_PROMOTION_SIGNALS):
        return True
    if any(signal in combined for signal in DIRECT_PROMOTION_SIGNALS):
        return True
    return any(event in title_text for event in EVENT_SIGNALS) and any(
        signal in combined for signal in PROMOTION_SIGNALS
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def event_level_points(title: str, content: str) -> float:
    text = normalize(f"{title} {content}")
    top = ("新药获批", "批准上市", "获批上市", "三期", "iii期", "ⅲ期", "主要终点",
           "并购", "重组", "许可交易", "授权交易", "撤市", "召回", "重大政策")
    high = ("临床进展", "临床结果", "二期", "ii期", "突破性疗法", "优先审评", "医保目录")
    medium = ("业绩", "融资", "合作", "产能", "商业化", "适应症")
    if any(x in text for x in top):
        return 25.0
    if any(x in text for x in high):
        return 20.0
    if any(x in text for x in medium):
        return 15.0
    return 8.0


def industry_impact_points(title: str, content: str) -> float:
    text = f"{title} {content}"
    quantified = bool(re.search(r"\d+(?:\.\d+)?\s*(?:亿|万|%|例|人|家|个品种|亿美元|亿元)", text))
    broad = any(x in text for x in ("全国", "全球", "行业", "市场规模", "患者", "供应链", "医保", "集采"))
    if quantified and broad:
        return 10.0
    if quantified:
        return 7.0
    if broad:
        return 5.0
    return 2.0


def scarcity_points(title: str, content: str) -> float:
    text = normalize(f"{title} {content}")
    if any(x in text for x in ("first-in-class", "全球首个", "全球首款", "中国首个", "国内首个", "首款获批", "首次获批")):
        return 5.0
    if any(x in text for x in ("首个", "首款", "首次", "突破性")):
        return 3.0
    return 0.0


def main() -> None:
    args = parse_args()
    anchor = datetime.strptime(args.anchor_date, "%Y-%m-%d").date() if args.anchor_date else date.today()
    range_start, range_end = current_cycle(anchor)
    selected_candidates: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for input_name in args.input:
        input_path = Path(input_name)
        for record in load_records(input_path):
            source = source_name(record, input_path)
            if not is_medalpha(source, input_path):
                continue
            title = str(first_value(record, TITLE_KEYS) or "").strip()
            url = str(first_value(record, URL_KEYS) or "").strip()
            source_content = str(first_value(record, CONTENT_KEYS) or "").strip()
            published = parse_datetime(first_value(record, DATE_KEYS))
            if not title or not url or not source_content or published is None:
                continue
            if not is_info_wechat_url(url):
                continue
            if not range_start <= published <= range_end:
                continue
            if is_invitation_or_event_promotion(title, source_content):
                rejected_candidates.append({"title": title, "article_url": url, "reason": "invitation_or_event_promotion"})
                continue
            key_url, key_title = normalize(url), normalize(title)
            if key_url in seen_urls or key_title in seen_titles:
                continue
            seen_urls.add(key_url)
            seen_titles.add(key_title)
            selected_candidates.append(
                {
                    "title": title,
                    "article_url": url,
                    "source": "医药魔方Info",
                    "published_at": published.isoformat(sep=" ", timespec="seconds"),
                    "source_content": source_content,
                    "source_evidence": str(nested_value(record, SOURCE_EVIDENCE_KEYS) or ""),
                    "source_capture_time": str(
                        nested_value(record, CAPTURE_TIME_KEYS)
                        or datetime.fromtimestamp(input_path.stat().st_mtime).isoformat(sep=" ", timespec="seconds")
                    ),
                    "raw": record,
                }
            )

    for item in selected_candidates:
        components = {
            "事件级别": event_level_points(item["title"], item["source_content"]),
            "产业影响": industry_impact_points(item["title"], item["source_content"]),
            "信息稀缺": scarcity_points(item["title"], item["source_content"]),
        }
        item["importance_components"] = components
        item["importance_score"] = round(sum(components.values()), 4)
        item["importance_formula"] = "事件级别25+产业影响10+信息稀缺5；同分按发布时间"
        item["content_verified"] = True
        item["evidence_status"] = "available" if item["source_evidence"] else "pending"
        del item["raw"]
    top_items = sorted(
        selected_candidates,
        key=lambda item: (item["importance_score"], item["published_at"]),
        reverse=True,
    )[: args.count]
    top_items.sort(key=lambda item: item["published_at"], reverse=True)
    output = {
        "range_start": range_start.date().isoformat(),
        "range_end": range_end.date().isoformat(),
        "count": len(top_items),
        "requested_count": args.count,
        "shortfall": max(0, args.count - len(top_items)),
        "content_status": "complete" if len(top_items) >= args.count else "shortfall",
        "evidence_status": "complete" if top_items and all(item["evidence_status"] == "available" for item in top_items) else "pending",
        "ranking_metric": "event_importance_industry_impact_scarcity_then_publish_time",
        "weight_profile": {"事件级别": 25, "产业影响": 10, "信息稀缺": 5},
        "engagement_metrics_used": False,
        "sources_used": ["医药魔方Info"] if top_items else [],
        "rejected": rejected_candidates,
        "items": top_items,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
