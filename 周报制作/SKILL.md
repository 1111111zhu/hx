---
name: huaxin-pharma-weekly-report
description: "Refresh a matched Huaxin Pharma weekly-report PPTX/XLSX pair, or one of its research, policy, industry-news, or company-announcement sections. Use when native editable tables, paired Excel evidence, direct-source links, and template fidelity must be preserved."
---

# Huaxin Pharma Weekly Report

Deliver one validated PPTX/XLSX pair. JSON and Markdown are intermediate records, not the final weekly-report deliverables. Use the user's supplied matched pair first; otherwise use the bundled `assets/templates/weekly-template.pptx` and `assets/templates/evidence-template.xlsx`. The bundled pair is a historical layout baseline; its old news is not verified current content. Never rebuild the workbook, flatten an editable PPT table, or invent missing source evidence.

For end-to-end industry-news production, read [references/通用规则/配对交付.md](references/通用规则/配对交付.md), then continue from selection through both saved Office files. `scripts/通用/配对产物.py prepare` creates portable working copies and an inventory; `check` rejects unchanged files and selected text/links that were never written. These structural checks do not replace source and visual verification.

## Start with the Input Contract

For a request to change rules or this skill, edit the instructions only. Generate or repair a report only when the user also requests that deliverable.

Before editing, read [references/通用规则/输入与交接.md](references/通用规则/输入与交接.md). Confirm that the task includes the actual skill bundle, one unambiguous approved PPTX/XLSX pair, an anchor date, the requested stage scope, and the source/access package required by that scope.

If the request was forwarded from another user or task, do not assume that local files, scripts, skills, browser sessions, or prior approvals were forwarded with the chat. Apply the readiness gate in the reference. Missing inputs block only the affected stage; they do not authorize lower-quality substitutes.

## Run Contract

1. Ignore `~$` lock files. Select one approved PPTX and its matched XLSX. If multiple plausible pairs exist and the approved pair cannot be inferred safely, stop before editing.
2. Create dated working copies and keep the originals unchanged. Each completed stage becomes the input checkpoint for the next stage.
3. Run `scripts/通用/周报预检.py` with the user-supplied anchor date and save `weekly_run_manifest.json` beside the working copies. The script-defined completed Saturday-through-Friday window is authoritative.
4. Inventory workbook sheet order, names, visibility, drawings and anchors, used ranges, print/page settings, and freeze panes. Non-target sheets must remain unchanged.
5. Locate PPT targets by their visible Chinese titles, never by fixed slide numbers.
6. Read [references/通用规则/内容规则总表.md](references/通用规则/内容规则总表.md) for the stage or stages being updated. The category folders under `references/行业新闻/`, `references/公司公告/`, and `references/政府政策/` provide quick routing notes.
7. Read [references/通用规则/证据版式质检.md](references/通用规则/证据版式质检.md) before changing PPT or Excel evidence. Its rules apply to every updated stage.
8. Checkpoint after each stage and reopen the saved artifacts before final validation.

## Stage State and Stop Rules

Use `pending`, `running`, `completed_content`, `evidence_pending`, `completed`, `content_shortfall`, `blocked_source`, or `failed_validation`.

- `completed_content`: selected content, dates, account identity, direct URLs, and topmost source paragraphs are verified and written; evidence images may still be pending.
- `evidence_pending`: content work remains valid, but one or more Excel evidence crops are not yet available or have not passed layout QA.
- `completed`: content, PPT, Excel evidence, links, and saved-file validation all pass.
- `content_shortfall`: fewer than the target number of individually verified, non-promotional in-window items are available; keep verified items and report the exact shortfall.
- `blocked_source`: no usable source access exists to verify any item for the affected stage.
- `failed_validation`: edited output exists but a required count, link, layout, text, or saved-file check fails.

Do not use an all-or-nothing rollback for Industry News. A missing reading count never blocks it, and a missing screenshot must not discard already verified content. Keep each verified new item, mark only its evidence as pending, clear rather than silently retain any stale old-week row that is not part of the new selection, and report any count shortfall. Never fabricate content or evidence. Other stages retain their existing stage-specific stop rules.

## Non-negotiable Invariants

- Preserve native editable tables, existing template chrome, and the matched Excel evidence structure.
- Treat exact source text, direct URLs, dates, stock codes, labels, and counts as data—not prose to improve.
- Do not summarize, infer, score with guessed metrics, or substitute secondary sources where the stage rules require exact extraction or an original source.
- Every updated item must bind its visible URL, hyperlink target, direct source, and captured source text in one record. Add and validate the screenshot in the evidence phase; its temporary absence does not invalidate verified Industry News content.
- Render and inspect the final saved files. In-memory or pre-save checks are insufficient.

## User-Confirmed Hard Rules

These rules come from the supplied case files and must be applied whenever the corresponding stage is touched:

- Treat the latest supplied case PPTX/XLSX as the visual authority. Compare every edited PPT page, including font family, font size, weight, alignment, table geometry, row height, page number, footer clearance, and blank-row behavior; do not rely on a verbal description of the style.
- Industry-news text must be derived from the topmost original paragraph from the verified 医药魔方Info article. Keep an untouched canonical copy. For PPT display, use the date stated in that first paragraph for the date column as month-day only; never use the article publication date and never add a year to the displayed event date. Do not add a date to the body. If the paragraph begins with that same date marker, remove only that leading marker from the PPT body. Delete a parenthetical segment only when the segment contains `以下简称`; keep other parenthetical content. Preserve all remaining wording, punctuation, figures, dates, and qualifiers exactly. The source crop ends at the paragraph's lower black boundary (including that boundary and everything above it) and excludes all later article text.
- Select 医药魔方Info items by event importance, industry impact, information scarcity, and publication time. Do not require, estimate, record, or rank by reading count, likes, or other interaction metrics. Exclude activities, invitations, registrations, agendas, conferences, livestream promotions, training, recruitment, advertisements, sponsorships, and equivalent non-industry-news content before selection.
- Company-announcement subjects shown in the PPT must be exactly four Chinese characters and must not use `业绩快报`. Use `业绩预告` for forecast/alert filings before actual results, and `业绩公告` for disclosed actual revenue/net-profit results, including material results filings whose original title says `业绩快报`. Prioritize `业绩公告`, `临床进展`, and large shareholder increase/decrease items when they are available. Exclude any filing whose source text says the matter does not or will not have a material impact on the company, regardless of title or topic. The body uses the smallest complete exact excerpt that contains the most material fact and figures. The first sentence must have an explicit subject; prefer the original filing's subject, and if the selected source fragment omits it, add the verified company short name as the minimal subject and log that addition separately. Minimal neutral connectors may join source fragments, but must be logged separately and must not add a fact, interpretation, or emphasis.
- Policy pages must follow the case table's native fonts, fills, column widths, row heights, page numbering, and source-bar gap. The date column uses month-day only, `发文机构` writes one lead agency only, and `主要内容` stays as concise as possible while remaining an exact source excerpt. Remove unused blank rows. For standalone government-policy lists, exclude all `公开征求意见`、`征求意见稿`、意见征集 or consultation-only notices unless the user explicitly asks for drafts; report a shortfall instead of replacing them with weaker items.
- For Industry Policy and Company Announcements only, select by materiality before recency. Policy materiality is defined by national reach, binding or implementation force, effect on payment/procurement/market access/regulatory rules, affected population or industry breadth, and size of the practical change. Company Announcements put material earnings disclosures, material clinical progress, and large shareholder increase/decrease disclosures in the highest priority tier; routine governance notices never displace them.
- For Industry Policy and Company Announcements only, every displayed substantive word must be copied from the original official file or detail page. Use extractive deletion only: do not paraphrase, generalize, infer, or add unsupported content. Keep the source wording and figures intact. For Company Announcements, the only permitted subject supplement is the verified company short name required to make the first sentence explicit, and it must be logged separately. Minimal neutral connectors may join source fragments; record each added connector separately so it cannot be mistaken for quoted source text.
- Every Industry Policy and Company Announcement source fragment must be completely visible in the matching right-side Excel evidence image or images. Logged neutral connectors are exempt from screenshot coverage. A source clause that is absent, cropped, illegible, or only visible in the left PPT-row image is unsupported and must be removed or recaptured before completion. Use separate pictures for non-contiguous passages or different pages; never stitch them. Insert multiple source pictures in source order, top-to-bottom first and left-to-right only if they cannot fit vertically; verify after saving that no two image rectangles intersect or cover each other.
- In Excel evidence sheets, the purple cell borders are the enclosure. Keep each left and right screenshot at natural aspect ratio and size; move or resize the purple frame/separator independently so each image's bottom is flush with its own frame. Never resize, stretch, pad, mask, or add thin image strips to make an image fit, and never move only one side of a shared separator. Never stitch multiple screenshots or page regions into one bitmap. When an item needs two or more source images, insert them as separate picture objects in source order with a visible gap; after reopening the workbook, verify pairwise that their absolute rectangles do not intersect or overlap.
- Show the direct official URL as visible text and as the hyperlink in the same cell. Source screenshots must include the source identity and the exact passage used, with no unrelated lower-page material or large blank canvas.

## Stage Router

Within each evidence item, source screenshots must follow the original file's page order and within-page reading order. Derive placement from verified source positions, normalize image anchors to their actual cells, and verify the saved visual order; filename, capture, insertion, or PPT excerpt order is not a substitute. See `Source Screenshot Order` in [references/通用规则/证据版式质检.md](references/通用规则/证据版式质检.md).

- `华鑫医药团队近期研究成果` + worksheet 1: Research Results.
- `近期行业重要政策` + `P22行业政策`: Industry Policy.
- both `近期行业要闻梳理` slides + `P23-24行业新闻`: Industry News.
- both `周重要上市公司公告一览` slides + `P25-26公司公告`: Company Announcements.

For a partial refresh, update only the named stage and preserve all other stages exactly.

## Delivery

Deliver one final PPTX/XLSX pair plus `weekly_run_manifest.json` and any validation/deviation records. Report each stage status, the selected weekly window, final item counts, and every blocked gate with its exact access or source reason.

## Bundled Scripts

- `scripts/通用/周报预检.py`: validate the pair and create the shared manifest.
- `scripts/研究成果/医药新观报告提取.py`: normalize an authorized 医药新观 feed/export.
- `scripts/政府政策/政策筛选.py`: filter and rank policy candidates only.
- `scripts/行业新闻/医药魔方新闻整理.py`: filter and rank the currently available verified 医药魔方Info candidates without engagement metrics; it reports content shortfall and evidence status separately.
- `scripts/行业新闻/微信证据截图裁剪.py`: crop WeChat evidence images.
- `scripts/公司公告/公告筛选.py`: filter and rank announcement candidates only.
- `scripts/通用/左侧行文本校验.py`: compare final PPT rows with Excel left evidence crops.

Run a script with `--help` before first use. Selection scripts may reject or rank candidates; they must never rewrite copied source text.
