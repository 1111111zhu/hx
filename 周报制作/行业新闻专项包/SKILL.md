---
name: huaxin-pharma-industry-news
description: "Update 华鑫医药周报行业新闻 / P23-24 from 医药魔方Info and deliver a matched editable PPTX and evidence XLSX using supplied or bundled templates. Includes source selection, exact first-paragraph text, non-overlapping evidence images, and saved-file QA. Use for industry-news refreshes; JSON-only selection is an explicit optional mode."
---

# Huaxin Pharma Industry News

Default deliverables for a weekly Industry News refresh are one updated editable PPTX and its matched evidence XLSX. JSON and Markdown are intermediate records, never substitutes for those files. This skill includes the paired templates and the complete production instructions; it does not require a sibling skill or the original author's computer.

Read [references/paired-delivery.md](references/paired-delivery.md) before starting production. An explicit request for selection/list/JSON only uses content-only mode. A request to diagnose or edit this skill changes the rules only, not a report. Respect explicitly requested single-file scope.

## Start Here

Read [references/industry-news-rules.md](references/industry-news-rules.md) completely before selecting, auditing, or writing Industry News content.

Required task inputs are:

- an explicit date range or an anchor date;
- access to original 医药魔方Info articles, or candidate records that contain their direct URLs and original text;
- use the user's latest supplied matched template pair, otherwise `assets/templates/weekly-template.pptx` and `assets/templates/evidence-template.xlsx`. These bundled files are historical layout examples, not current verified news.

If only an anchor date is supplied, use the most recently completed Saturday-through-Friday window. Do not guess a different historical week.

## Workflow

1. Discover candidates from the currently available source route. Do not require a preassembled complete pool before starting.
2. Verify each candidate independently: visible account identity `医药魔方Info`, in-window publication time, openable original WeChat URL, and the complete topmost original paragraph.
3. Reject promotional or non-news content before ranking. Apply the exclusion list in the reference even when the post mentions an important medical topic.
4. Rank qualified candidates by event importance, industry impact, information scarcity, then publication time. Never use reading count, likes, shares, comments, or engagement rate.
5. Target 10 items. Keep every verified item; if fewer than 10 qualify, report the exact shortfall and never reuse old-week items or fabricate replacements.
6. Preserve an untouched canonical copy of the topmost original paragraph. In PPT, use the first paragraph's date for the date column as month-day only instead of the article publication date; do not add a year to the displayed event date, do not add a date to the body, remove only a leading date marker when that same marker has been moved to the date column, and delete only parenthetical segments that contain `以下简称`.
7. Track content verification and screenshot evidence separately. A missing screenshot sets `evidence_pending`; it does not invalidate verified content or roll the whole section back.

For JSON/CSV-normalized inputs, run `scripts/select_weekly_news.py --help` before first use. The script filters dates and promotions, scores candidates without engagement metrics, and reports content and evidence states separately.

## Produce the Pair

After selection, continue automatically through native PPT table replacement, saved-slide rendering, mechanical row crops, Excel source evidence insertion, and reopening/validation. Follow `references/paired-delivery.md` and `references/evidence-layout-qa.md`. Do not stop at the selector output or ask whether the user also wants PPT and Excel during a weekly-report refresh. Evidence images remain separate, non-overlapping objects. Missing evidence permits a clearly labelled partial pair; it never permits a false completion claim.

## Completion

Within each item, place source screenshots in the original article's reading order. Verify source positions, normalized cell anchors, and the saved visual order as specified in `Source Screenshot Order` in [references/evidence-layout-qa.md](references/evidence-layout-qa.md).

- `completed_content`: all selected item content passed source verification.
- `content_shortfall`: fewer than 10 items passed; retain verified items and report the gap.
- `evidence_pending`: selected content is valid but one or more evidence crops are missing or failed layout QA.
- `completed`: selected content and all requested artifact/evidence checks passed.
- `blocked_source`: no usable route can verify any original 医药魔方Info item.

Only `blocked_source` stops content selection entirely. Missing reading metrics never block this skill.
