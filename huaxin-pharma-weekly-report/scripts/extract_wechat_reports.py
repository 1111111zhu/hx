#!/usr/bin/env python3
"""Extract 医药新观 深度报告 and 点评报告 items from JSON/RSS/Atom feeds."""

from __future__ import annotations

import argparse
import email.utils
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


XML_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

DEPTH_RE = re.compile(r"(深度报告|深度|行业深度|公司深度)")
COMMENT_RE = re.compile(r"(点评报告|点评|事件点评|公司点评|行业点评|快评)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Feed URL or local JSON/RSS/Atom/XML file.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--depth-limit", type=int, default=0, help="Max 深度报告 items; 0 keeps all.")
    parser.add_argument("--comment-limit", type=int, default=0, help="Max 点评报告 items; 0 keeps all.")
    args = parser.parse_args()

    payload = read_input(args.input)
    items = parse_feed(payload)
    grouped = classify(items)
    grouped["深度报告"] = cap(sort_items(grouped["深度报告"]), args.depth_limit)
    grouped["点评报告"] = cap(sort_items(grouped["点评报告"]), args.comment_limit)

    Path(args.out).write_text(json.dumps(grouped, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def read_input(value: str) -> bytes:
    if re.match(r"^https?://", value):
        request = urllib.request.Request(
            value,
            headers={
                "User-Agent": "huaxin-pharma-research-skill/1.0",
                "Accept": "application/json, application/rss+xml, application/atom+xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    return Path(value).read_bytes()


def parse_feed(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return []
    if text[0] in "[{":
        return parse_json(json.loads(text))
    return parse_xml(text)


def parse_json(data: Any) -> list[dict[str, str]]:
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        raw_items = data.get("items") or data.get("data") or data.get("articles") or data.get("entries") or []
    else:
        raw_items = []

    items: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = first(raw, "title", "name")
        url = first(raw, "url", "link", "mp_url", "article_url")
        published_at = normalize_date(first(raw, "published_at", "pubDate", "pub_date", "date", "created_at", "updated_at"))
        category = first(raw, "category", "type", "column", "tag")
        summary = first(raw, "summary", "description", "digest", "content")
        items.append(clean_item(title, url, published_at, category, summary))
    return items


def parse_xml(text: str) -> list[dict[str, str]]:
    root = ElementTree.fromstring(text)
    if root.tag.endswith("feed"):
        entries = root.findall("atom:entry", XML_NS) or root.findall("entry")
        return [parse_atom_entry(entry) for entry in entries]
    return [parse_rss_item(item) for item in root.findall(".//item")]


def parse_atom_entry(entry: ElementTree.Element) -> dict[str, str]:
    url = ""
    for link in entry.findall("atom:link", XML_NS) + entry.findall("link"):
        if link.attrib.get("rel", "alternate") == "alternate":
            url = link.attrib.get("href", "")
            break
    title = text_of(entry, "atom:title", "title")
    published_at = normalize_date(text_of(entry, "atom:published", "atom:updated", "published", "updated"))
    summary = text_of(entry, "atom:summary", "atom:content", "summary", "content")
    category = " ".join(node.attrib.get("term", "") for node in entry.findall("atom:category", XML_NS))
    return clean_item(title, url, published_at, category, summary)


def parse_rss_item(item: ElementTree.Element) -> dict[str, str]:
    title = text_of(item, "title")
    url = text_of(item, "link")
    published_at = normalize_date(text_of(item, "pubDate", "date"))
    category = text_of(item, "category")
    summary = text_of(item, "description", "content:encoded")
    return clean_item(title, url, published_at, category, summary)


def clean_item(title: str, url: str, published_at: str, category: str, summary: str) -> dict[str, str]:
    return {
        "title": clean(title),
        "url": clean(url),
        "published_at": clean(published_at),
        "category": clean(category),
        "summary": strip_html(summary),
    }


def classify(items: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped = {"深度报告": [], "点评报告": []}
    seen: set[tuple[str, str]] = set()
    for item in items:
        haystack = " ".join([item.get("title", ""), item.get("category", ""), item.get("summary", "")])
        key = (item.get("url", ""), normalize_title(item.get("title", "")))
        if key in seen:
            continue
        seen.add(key)
        public_item = {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published_at": item.get("published_at", ""),
        }
        if DEPTH_RE.search(haystack):
            grouped["深度报告"].append(public_item)
        elif COMMENT_RE.search(haystack):
            grouped["点评报告"].append(public_item)
    return grouped


def sort_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(items, key=lambda item: date_sort_key(item.get("published_at", "")), reverse=True)


def cap(items: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    return items if limit <= 0 else items[:limit]


def normalize_date(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except (TypeError, ValueError):
        return value


def date_sort_key(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def first(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return str(value)
    return ""


def text_of(node: ElementTree.Element, *paths: str) -> str:
    for path in paths:
        found = node.find(path, XML_NS)
        if found is not None and found.text:
            return found.text
    return ""


def clean(value: Any) -> str:
    return html.unescape(str(value or "")).strip()


def strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", "", value or "").casefold()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
