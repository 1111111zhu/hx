---
name: huaxin-pharma-industry-news
description: "Select, verify, rank, and package the Industry News section of a Huaxin pharmaceutical weekly report from original 医药魔方Info articles. Use for 华鑫医药周报行业新闻, P23-24行业新闻, 医药魔方Info weekly selection, first-paragraph extraction, promotional-content filtering, or evidence-status repair."
---

# Huaxin Pharma Industry News

Produce an auditable weekly Industry News selection without using reading counts or interaction metrics. This skill is self-contained and may be used alone or alongside presentation/spreadsheet tooling when the user also requests artifact edits.

## Start Here

Read [references/industry-news-rules.md](references/industry-news-rules.md) completely before selecting, auditing, or writing Industry News content.

Required task inputs are:

- an explicit date range or an anchor date;
- access to original 医药魔方Info articles, or candidate records that contain their direct URLs and original text;
- the target artifact only when the user asks for PPTX/XLSX changes.

If only an anchor date is supplied, use the most recently completed Saturday-through-Friday window. Do not guess a different historical week.

## Workflow

1. Discover candidates from the currently available source route. Do not require a preassembled complete pool before starting.
2. Verify each candidate independently: visible account identity `医药魔方Info`, in-window publication time, openable original WeChat URL, and the complete topmost original paragraph.
3. Reject promotional or non-news content before ranking. Apply the exclusion list in the reference even when the post mentions an important medical topic.
4. Rank qualified candidates by event importance, industry impact, information scarcity, then publication time. Never use reading count, likes, shares, comments, or engagement rate.
5. Target 10 items. Keep every verified item; if fewer than 10 qualify, report the exact shortfall and never reuse old-week items or fabricate replacements.
6. Preserve the topmost original paragraph verbatim. Do not summarize, shorten, reorder, prepend a headline, or add analysis.
7. Track content verification and screenshot evidence separately. A missing screenshot sets `evidence_pending`; it does not invalidate verified content or roll the whole section back.

For JSON/CSV-normalized inputs, run `scripts/select_weekly_news.py --help` before first use. The script filters dates and promotions, scores candidates without engagement metrics, and reports content and evidence states separately.

## Artifact Boundary

Do not edit PPTX/XLSX unless the user asks for artifact changes. When artifact changes are requested, preserve the supplied template and use the relevant presentation/spreadsheet capability. Evidence images must remain separate picture objects, must not be stitched, and must not overlap.

## Completion

- `completed_content`: all selected item content passed source verification.
- `content_shortfall`: fewer than 10 items passed; retain verified items and report the gap.
- `evidence_pending`: selected content is valid but one or more evidence crops are missing or failed layout QA.
- `completed`: selected content and all requested artifact/evidence checks passed.
- `blocked_source`: no usable route can verify any original 医药魔方Info item.

Only `blocked_source` stops content selection entirely. Missing reading metrics never block this skill.
