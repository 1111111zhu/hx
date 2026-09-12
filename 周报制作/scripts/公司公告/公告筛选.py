#!/usr/bin/env python3
"""Select weekly pharma announcements by tier and an exact four-Chinese-character PPT subject."""

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
REQUIRED = ("published_at", "code", "company_name", "subject", "main_content", "original_file_url")
SOURCE_KEYS = ("source", "source_name", "provider")
DATE_KEYS = ("published_at", "disclosed_at", "publish_time", "announcement_time", "date", "time")
CODE_KEYS = ("code", "stock_code", "security_code", "ticker")
COMPANY_KEYS = ("company_name", "short_name", "security_name", "company")
SUBJECT_KEYS = ("subject", "title", "announcement_title", "headline")
CONTENT_KEYS = ("canonical_text", "original_text", "excerpt", "main_content", "content", "body")
ORIGINAL_URL_KEYS = ("original_file_url", "file_url", "attachment_url", "announcement_url", "url", "link")
RECORD_URL_KEYS = ("record_url", "source_url", "page_url", "origin_url")
INDUSTRY_KEYS = ("industry", "industry_name", "sector", "classification")
MARKET_KEYS = ("market", "exchange", "listing_market", "stock_exchange")
SCORE_KEYS = ("impact_score", "score", "importance", "heat")
MATERIALITY_TIER_KEYS = ("materiality_tier", "impact_tier", "materiality", "impact_level")
MATERIALITY_RATIONALE_KEYS = ("materiality_rationale", "impact_rationale", "impact_reason")
HALF_YEAR_MARKERS = ("半年度报告", "半年报", "半年度业绩", "中期业绩", "中报")

PHARMA_MARKERS = ("医药", "生物", "医疗", "制药", "药品", "中药", "器械", "CRO", "CDMO", "医药生物")
EXCLUDED_MARKERS = ("银行", "证券", "保险", "房地产", "煤炭", "钢铁", "有色", "汽车", "传媒", "食品饮料")
IMPACT_WEIGHTS = {
    "实际控制人": 40, "控股股东": 38, "大股东": 32, "持股": 30, "减持": 34, "增持": 32,
    "股权转让": 34, "要约收购": 38, "控制权": 40, "质押": 28, "冻结": 28,
    "重大资产重组": 38, "并购": 36, "收购": 36, "重大投资": 30, "融资": 28,
    "回购": 25, "注销": 25, "业绩预告": 48, "营业收入": 42, "归母净利润": 46, "利润": 34, "亏损": 40,
    "担保": 22, "诉讼": 27, "处罚": 28, "立案": 30, "退市": 40, "停牌": 30,
    "获批": 24, "上市申请": 23, "临床": 38, "合作": 18, "授权": 22,
    "全球首个": 48, "全球首款": 48, "关键性临床": 38, "iii期": 36, "ⅲ期": 36,
    "首例患者": 30, "主要终点": 34, "全部研究终点": 38, "所有研究终点": 38,
    "fda": 34, "ema": 34, "快速通道": 32, "突破性疗法": 34,
    "nature": 34, "nejm": 34, "lancet": 34, "保护效力": 28,
}
CONTROL_MARKERS = (
    "实际控制人变更", "实控人变更", "控制权变更", "控股股东变更", "要约收购", "股权转让", "表决权委托",
    "破产重整", "退市风险", "终止上市",
)
MAJOR_TRANSACTION_MARKERS = (
    "重大资产重组", "构成重大资产重组", "发行股份购买资产", "吸收合并", "借壳",
    "重大收购", "重大出售", "重大投资", "重大融资",
)
MAJOR_FINANCIAL_LEGAL_MARKERS = (
    "业绩预告", "巨额亏损", "债务违约", "无法清偿", "审计意见", "保留意见", "否定意见",
    "重大诉讼", "重大仲裁", "立案调查", "行政处罚", "强制退市", "停牌核查",
)
MAJOR_PRODUCT_MARKERS = (
    "获批上市", "批准上市", "药品注册证书", "医疗器械注册证", "商业化上市", "首款上市",
    "iii期", "ⅲ期", "3期", "注册性临床", "主要终点", "关键性临床", "高价值授权",
)
ROUTINE_MARKERS = (
    "申请获受理", "申请受理", "补充申请", "一致性评价", "完成备案", "许可证续期", "日常经营", "常规进展",
    "董事会决议", "监事会决议", "股东大会通知", "股东大会决议", "月度经营", "提示性公告",
)
EXPLICIT_MAJOR_TIERS = ("major", "critical", "high", "重大", "极高", "核心")
NO_MATERIAL_IMPACT_MARKERS = (
    "不构成重大影响", "不会产生重大影响", "不产生重大影响", "无重大影响", "没有重大影响",
    "不会对公司产生重大影响", "不影响公司正常经营", "不构成重大资产重组",
)
NO_MATERIAL_IMPACT_PATTERNS = (
    re.compile(r"(?:不|不会|未|预计不会|预计不).{0,40}对(?:本)?公司.{0,40}产生(?:重大|重大不利)?影响"),
    re.compile(r"对(?:本)?公司.{0,40}(?:不产生|不会产生|未产生)(?:重大|重大不利)?影响"),
)
SHAREHOLDER_CHANGE_LABELS = {"股东增持", "股东减持"}
FIRST_TIER_LABELS = {
    "业绩预告": ("业绩预告", "盈利预警", "预计亏损", "预亏"),
    "业绩公告": ("业绩公告", "业绩快报", "半年度报告", "年度报告摘要", "季度报告", "营业收入", "归属于上市公司股东的净利润", "归母净利润"),
    "新药获批": ("新药获批", "获批上市", "批准上市", "药品注册证书", "首次商业化上市"),
    "临床进展": (
        "临床进展", "临床试验", "临床获批", "ind获批", "达到主要终点", "完成入组",
        "首例患者入组", "首例患者给药", "所有研究终点", "全部研究终点", "顶线结果",
        "iii期", "ⅲ期", "3期", "注册性临床", "关键性临床", "nature communications",
    ),
    "海外获批": (
        "海外获批", "fda批准", "fda获批", "ema批准", "ema获批", "快速通道资格",
        "fast track", "获准在美国开展临床", "获批在美国开展临床", "海外临床试验批准",
    ),
    "并购重组": ("并购重组", "重大资产重组", "发行股份购买资产", "吸收合并", "收购资产"),
    "专利到期": ("专利到期", "专利届满", "专利失效"),
    "专利获批": ("专利获批", "获得专利", "专利授权"),
    "股东增持": ("股东增持", "增持股份", "增持计划"),
    "股东减持": ("股东减持", "减持股份", "减持计划"),
    "控制变更": ("控制权变更", "实控人变更", "实际控制人变更", "控股股东变更"),
    "许可交易": ("许可交易", "授权许可", "对外授权", "license-out", "高价值授权"),
    "许可终止": ("许可终止", "终止许可", "终止授权", "授权终止"),
    "临床失败": ("临床失败", "未达主要终点", "主要终点未达", "临床终止", "停止临床"),
    "产品退市": ("产品退市", "停止销售", "撤回上市", "注销注册证"),
    "安全警示": ("安全警示", "黑框警告", "严重不良反应", "安全性风险"),
    "破产重整": ("破产重整", "申请重整", "预重整"),
    "退市风险": ("退市风险", "终止上市", "强制退市"),
    "重大诉讼": ("重大诉讼", "重大仲裁"),
    "债务违约": ("债务违约", "无法清偿", "逾期债务"),
    "审计非标": ("审计非标", "保留意见", "否定意见", "无法表示意见"),
    "重大处罚": ("重大处罚", "行政处罚", "立案调查"),
    "产品召回": ("产品召回", "药品召回", "器械召回"),
    "核心停产": ("核心停产", "停产整顿", "主要产品停产"),
    "质押风险": ("质押风险", "高比例质押", "质押违约"),
    "股份冻结": ("股份冻结", "司法冻结", "轮候冻结"),
}
SECOND_TIER_LABELS = {
    "定增获批": ("定增获批", "向特定对象发行", "同意注册批复"),
    "股权转让": ("股权转让", "协议转让"),
    "股份回购": ("股份回购", "回购股份"),
    "股份注销": ("股份注销", "注销股份"),
    "重大投资": ("重大投资", "项目投资"),
    "资产出售": ("资产出售", "出售资产", "资产处置"),
    "债务重组": ("债务重组",),
    "资产减值": ("资产减值", "减值准备"),
    "商誉减值": ("商誉减值",),
    "股权激励": ("股权激励", "限制性股票激励"),
    "医保纳入": ("医保纳入", "纳入医保", "医保目录"),
    "集采中标": ("集采中标", "中选集采", "带量采购中选"),
}

TOP_PRIORITY_LABELS = {"业绩预告", "业绩公告", "临床进展", "临床失败", "股东增持", "股东减持"}
SECOND_PRIORITY_LABELS = {"新药获批", "海外获批", "并购重组", "控制变更", "许可交易", "许可终止"}
THIRD_PRIORITY_LABELS = {
    "破产重整", "退市风险", "重大诉讼", "债务违约", "审计非标", "重大处罚",
    "产品召回", "核心停产", "质押风险", "股份冻结", "定增获批", "股权转让",
    "重大投资", "资产出售", "债务重组", "资产减值", "商誉减值",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, action="append", help="JSON candidate export; repeat for 巨潮资讯网 and 同花顺.")
    parser.add_argument("--anchor-date", help="YYYY-MM-DD; defaults to today.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--count", type=int, default=10, help="Required number of selected items; default 10.")
    parser.add_argument("--half-year-majority", action="store_true", help="Require half-year reports to form a majority when the eligible pool permits.")
    return parser.parse_args()


def first_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "records", "data", "results", "announcements"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    raise ValueError(f"Unsupported JSON shape: {path}")


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", text)
    if match:
        y, m, d, h, minute, second = match.groups()
        return datetime(int(y), int(m), int(d), int(h or 0), int(minute or 0), int(second or 0))
    return None


def active_cycle(anchor: date) -> tuple[datetime, datetime]:
    days_since_friday = (anchor.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    end_day = anchor - timedelta(days=days_since_friday)
    start_day = end_day - timedelta(days=6)
    return datetime.combine(start_day, time.min), datetime.combine(end_day, time.max)


def source_from(record: dict[str, Any], path: Path) -> str:
    value = str(first_value(record, SOURCE_KEYS) or "").strip()
    if value:
        return value
    lowered = path.stem.lower()
    if "cninfo" in lowered or "巨潮" in lowered:
        return "巨潮资讯网"
    if "ths" in lowered or "tonghuashun" in lowered or "同花顺" in lowered:
        return "同花顺"
    if "hkex" in lowered or "港交所" in lowered or "香港交易所" in lowered:
        return "港交所"
    if "company" in lowered or "issuer" in lowered or "ir" in lowered:
        return "公司官网"
    return path.stem


def valid_source(source: str) -> bool:
    normalized = source.lower()
    return any(
        marker in normalized
        for marker in ("cninfo", "ths", "hkex", "company", "investor relations", "ir")
    ) or any(marker in source for marker in ("巨潮", "同花顺", "港交所", "香港交易所", "公司官网", "公司公告"))


def is_official_original_url(record: dict[str, Any], source: str, url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if host.endswith("cninfo.com.cn") or host.endswith("hkexnews.hk") or host.endswith("hkex.com.hk"):
        return True
    explicit = record.get("official_source")
    if explicit is True or str(explicit).strip().lower() in {"true", "1", "yes", "official", "是"}:
        return True
    return any(marker in source for marker in ("公司官网", "公司公告")) or any(
        marker in source.lower() for marker in ("company", "investor relations", "ir")
    )


def is_h_share(record: dict[str, Any], source: str, url: str, code: str) -> bool:
    market = str(first_value(record, MARKET_KEYS) or "").strip().lower()
    return code.isdigit() and len(code) == 5 and (
        any(marker in market for marker in ("hk", "hong kong", "h-share", "h share", "港股", "香港", "h股"))
        or "hkex" in source.lower()
        or "港交所" in source
        or "香港交易所" in source
        or "hkex" in url.lower()
    )


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def is_pharma(record: dict[str, Any], company: str, subject: str) -> bool:
    industry = str(first_value(record, INDUSTRY_KEYS) or "")
    joined = f"{industry} {company} {subject}"
    if any(marker in industry for marker in EXCLUDED_MARKERS):
        return False
    # Require an explicit industry classification unless the export already marks the item as pharma.
    return any(marker.lower() in joined.lower() for marker in PHARMA_MARKERS)


def impact_score(subject: str, content: str, supplied: float | None) -> float:
    if supplied is not None:
        return supplied
    text = f"{subject} {content}".lower()
    return float(sum(weight for word, weight in IMPACT_WEIGHTS.items() if word.lower() in text))


def classify_priority(subject: str, content: str) -> tuple[int, str] | None:
    text = f"{subject} {content}".lower()
    labels = {**FIRST_TIER_LABELS, **SECOND_TIER_LABELS}
    preferred_order = ["业绩预告", "业绩公告", "临床失败", "临床进展", "股东增持", "股东减持"]
    ordered = preferred_order + [label for label in labels if label not in preferred_order]
    for label in ordered:
        if any(marker.lower() in text for marker in labels[label]):
            if label in TOP_PRIORITY_LABELS:
                return 1, label
            if label in SECOND_PRIORITY_LABELS:
                return 2, label
            if label in THIRD_PRIORITY_LABELS:
                return 3, label
            return 4, label
    return None


def max_percent(text: str) -> float:
    values = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
    return max(values, default=0.0)


def max_amount_cny(text: str) -> float:
    amounts: list[float] = []
    for value, unit in re.findall(r"([\d,]+(?:\.\d+)?)\s*(亿元|亿|万元|万)", text):
        number = float(value.replace(",", ""))
        amounts.append(number * (100_000_000 if unit in ("亿元", "亿") else 10_000))
    return max(amounts, default=0.0)


def has_no_material_impact(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return any(marker in compact for marker in NO_MATERIAL_IMPACT_MARKERS) or any(
        pattern.search(compact) for pattern in NO_MATERIAL_IMPACT_PATTERNS
    )


def is_large_shareholder_change(text: str, amount: float, percent: float) -> bool:
    compact = re.sub(r"\s+", "", text)
    return (
        "大额" in compact
        or "持股5%以上" in compact
        or "5%以上股东" in compact
        or amount >= 100_000_000
        or percent >= 5
    )


def materiality_gate(
    raw: dict[str, Any], subject: str, content: str, supplied_score: float | None
) -> tuple[bool, float, str]:
    text = f"{subject} {content}".lower()
    explicit_tier = str(first_value(raw, MATERIALITY_TIER_KEYS) or "").strip().lower()
    explicit_reason = str(first_value(raw, MATERIALITY_RATIONALE_KEYS) or "").strip()
    amount = max_amount_cny(text)
    percent = max_percent(text)
    classified = classify_priority(subject, content)

    if has_no_material_impact(text):
        return False, 0.0, "公告原文明确表示不对公司产生重大影响，按硬规则排除。"
    if classified is not None:
        tier, label = classified
        if label in SHAREHOLDER_CHANGE_LABELS and not is_large_shareholder_change(text, amount, percent):
            return False, 0.0, "股东增减持未达到大额金额、比例或5%以上股东等优先条件。"
        score = {1: 120.0, 2: 90.0, 3: 75.0, 4: 60.0}[tier]
        return True, score, f"属于第{tier}优先梯队“{label}”；最终材料性仍须结合核心业务/管线和量化结果复核。"

    if explicit_reason and any(marker in explicit_tier for marker in EXPLICIT_MAJOR_TIERS):
        return True, max(float(supplied_score or 0), 80.0), explicit_reason
    if any(marker.lower() in text for marker in CONTROL_MARKERS):
        return True, 90.0, "涉及控制权、实际控制人、破产重整或退市风险。"
    if any(marker.lower() in text for marker in MAJOR_TRANSACTION_MARKERS):
        return True, 85.0, "涉及重大资产交易、重组、收购、出售、投资或融资。"
    if any(marker.lower() in text for marker in MAJOR_FINANCIAL_LEGAL_MARKERS):
        return True, 80.0, "涉及重大财务、偿债、审计、诉讼、处罚或退市事项。"
    if ("质押" in text or "冻结" in text) and percent >= 20:
        return True, 78.0, f"股权质押或冻结比例达到{percent:g}%，可能影响股东稳定性或控制权。"
    if any(marker in text for marker in ("增持", "减持", "回购", "注销")) and (amount >= 100_000_000 or percent >= 5):
        return True, 72.0, "股份变动、回购或注销达到显著金额或比例。"
    if any(marker.lower() in text for marker in MAJOR_PRODUCT_MARKERS):
        return True, 70.0, "涉及核心产品上市、关键性/III期临床结果或高价值商业化事件。"
    if amount >= 500_000_000:
        return True, 75.0, "披露交易、投资、融资、诉讼或经营事项金额达到5亿元。"
    if any(marker.lower() in text for marker in ROUTINE_MARKERS):
        return False, 0.0, "属于常规审批、会议、备案、专利或一般经营进展。"
    if supplied_score is not None and supplied_score >= 60 and explicit_reason:
        return True, supplied_score, explicit_reason
    return False, 0.0, "未能从公告原文证明其足以显著影响公司控制权、资产、财务、经营、核心产品或估值。"


def normalized_record(raw: dict[str, Any], path: Path) -> dict[str, Any] | None:
    published = parse_datetime(first_value(raw, DATE_KEYS))
    code = str(first_value(raw, CODE_KEYS) or "").strip()
    company = str(first_value(raw, COMPANY_KEYS) or "").strip()
    subject = str(first_value(raw, SUBJECT_KEYS) or "").strip()
    content = str(first_value(raw, CONTENT_KEYS) or "").strip()
    original_url = str(first_value(raw, ORIGINAL_URL_KEYS) or "").strip()
    source = source_from(raw, path)
    if not all((published, code, company, subject, content, original_url)) or not valid_source(source):
        return None
    if not is_official_original_url(raw, source, original_url):
        return None
    if not is_pharma(raw, company, subject):
        return None
    supplied = as_number(first_value(raw, SCORE_KEYS))
    material, gate_score, rationale = materiality_gate(raw, subject, content, supplied)
    if not material:
        return None
    priority = classify_priority(subject, content)
    if priority is None:
        return None
    priority_tier, subject_label = priority
    if len(subject_label) != 4 or not all("\u4e00" <= ch <= "\u9fff" for ch in subject_label):
        raise ValueError(f"Announcement PPT subject must be exactly 4 Chinese characters: {subject_label}")
    return {
        "published_at": published.isoformat(sep=" ", timespec="seconds"),
        "code": (
            code
            if is_h_share(raw, source, original_url, code)
            else code.zfill(6) if code.isdigit() and len(code) < 6 else code
        ),
        "company_name": company,
        "subject": subject_label,
        "announcement_title": subject,
        "is_half_year": any(marker.lower() in f"{subject} {content}".lower() for marker in HALF_YEAR_MARKERS),
        "priority_tier": priority_tier,
        "main_content": content,
        "original_file_url": original_url,
        "record_url": str(first_value(raw, RECORD_URL_KEYS) or "").strip(),
        "sources": [source],
        "record_urls": [str(first_value(raw, RECORD_URL_KEYS) or "").strip()],
        "industry": str(first_value(raw, INDUSTRY_KEYS) or "").strip(),
        "market": str(first_value(raw, MARKET_KEYS) or "").strip(),
        "source": source,
        "impact_score": max(impact_score(subject, content, supplied), gate_score),
        "materiality_rationale": rationale,
        "raw": raw,
    }


def main() -> None:
    args = parse_args()
    anchor = datetime.strptime(args.anchor_date, "%Y-%m-%d").date() if args.anchor_date else date.today()
    start, end = active_cycle(anchor)
    merged: dict[str, dict[str, Any]] = {}
    for input_name in args.input:
        path = Path(input_name)
        for raw in load_records(path):
            record = normalized_record(raw, path)
            if record is None:
                continue
            published = datetime.fromisoformat(record["published_at"])
            if not start <= published <= end:
                continue
            dedupe_key = normalize(record["original_file_url"]) or f"{record['code']}|{normalize(record['subject'])}"
            existing = merged.get(dedupe_key)
            if existing is None:
                merged[dedupe_key] = record
                continue
            if record["source"] not in existing["sources"]:
                existing["sources"].append(record["source"])
            if record["record_url"] and record["record_url"] not in existing["record_urls"]:
                existing["record_urls"].append(record["record_url"])
            if record["impact_score"] > existing["impact_score"]:
                existing["impact_score"] = record["impact_score"]
            if record["source"] == "巨潮资讯网":
                existing["main_content"] = record["main_content"]
                existing["original_file_url"] = record["original_file_url"]
                existing["source"] = record["source"]
                existing["record_url"] = record["record_url"]
    candidates = list(merged.values())
    rank_key = lambda item: (
        -item["impact_score"],
        -datetime.fromisoformat(item["published_at"]).timestamp(),
    )
    tier_rank_key = lambda item: (item["priority_tier"],) + rank_key(item)
    if args.half_year_majority:
        required_half_year = args.count // 2 + 1
        half_year = sorted((item for item in candidates if item["is_half_year"]), key=rank_key)
        selected = half_year[:required_half_year]
        selected_ids = {id(item) for item in selected}
        fill_pool = sorted((item for item in candidates if id(item) not in selected_ids), key=tier_rank_key)
        selected.extend(fill_pool[: max(0, args.count - len(selected))])
    else:
        required_half_year = 0
        selected = sorted(candidates, key=tier_rank_key)[: args.count]
    selected.sort(key=lambda item: item["published_at"], reverse=True)
    output = {
        "range_start": start.date().isoformat(),
        "range_end": end.date().isoformat(),
        "count": len(selected),
        "required_count": args.count,
        "shortfall": max(0, args.count - len(selected)),
        "half_year_majority_requested": args.half_year_majority,
        "half_year_count": sum(1 for item in selected if item["is_half_year"]),
        "half_year_shortfall": max(0, required_half_year - sum(1 for item in selected if item["is_half_year"])),
        "sources_used": sorted({source for item in selected for source in item["sources"]}),
        "items": selected,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
