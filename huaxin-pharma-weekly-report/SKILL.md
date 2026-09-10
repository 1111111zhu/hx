---
name: huaxin-pharma-weekly-report
description: "Refresh a matched Huaxin Pharma weekly-report PPTX/XLSX pair, or one of its research, policy, industry-news, or company-announcement sections. Use when native editable tables, paired Excel evidence, direct-source links, and template fidelity must be preserved."
---

# Huaxin Pharma Weekly Report

Deliver one validated PPTX/XLSX pair. JSON and Markdown are intermediate records, not the final weekly-report deliverables. Use the user's supplied matched pair first; otherwise use the bundled `assets/templates/weekly-template.pptx` and `assets/templates/evidence-template.xlsx`. The bundled pair is a historical layout baseline; its old news is not verified current content. Never rebuild the workbook, flatten an editable PPT table, or invent missing source evidence.

For end-to-end industry-news production, read [references/paired-delivery.md](references/paired-delivery.md), then continue from selection through both saved Office files. `scripts/paired_artifacts.py prepare` creates portable working copies and an inventory; `check` rejects unchanged files and selected text/links that were never written. These structural checks do not replace source and visual verification.

## Start with the Input Contract

Before editing, read [references/input-and-handoff.md](references/input-and-handoff.md). Confirm that the task includes the actual skill bundle, one unambiguous approved PPTX/XLSX pair, an anchor date, the requested stage scope, and the source/access package required by that scope.

If the request was forwarded from another user or task, do not assume that local files, scripts, skills, browser sessions, or prior approvals were forwarded with the chat. Apply the readiness gate in the reference. Missing inputs block only the affected stage; they do not authorize lower-quality substitutes.

## Run Contract

1. Ignore `~$` lock files. Select one approved PPTX and its matched XLSX. If multiple plausible pairs exist and the approved pair cannot be inferred safely, stop before editing.
2. Create dated working copies and keep the originals unchanged. Each completed stage becomes the input checkpoint for the next stage.
3. Run `scripts/preflight_weekly_report.py` with the user-supplied anchor date and save `weekly_run_manifest.json` beside the working copies. The script-defined completed Saturday-through-Friday window is authoritative.
4. Inventory workbook sheet order, names, visibility, drawings and anchors, used ranges, print/page settings, and freeze panes. Non-target sheets must remain unchanged.
5. Locate PPT targets by their visible Chinese titles, never by fixed slide numbers.
6. Read [references/content-rules.md](references/content-rules.md) for the stage or stages being updated.
7. Read [references/evidence-layout-qa.md](references/evidence-layout-qa.md) before changing PPT or Excel evidence. Its rules apply to every updated stage.
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
- Industry-news text must be derived from the topmost original paragraph from the verified 医药魔方Info article. Keep an untouched canonical copy. For PPT display, use the date stated in that first paragraph for the date column, never the article publication date; do not add a date to the body. If the paragraph begins with that same date marker, remove only that leading marker from the PPT body and preserve the remaining wording, punctuation, figures, and qualifiers exactly. The source crop ends at the paragraph's lower black boundary (including that boundary and everything above it) and excludes all later article text.
- Select 医药魔方Info items by event importance, industry impact, information scarcity, and publication time. Do not require, estimate, record, or rank by reading count, likes, or other interaction metrics. Exclude activities, invitations, registrations, agendas, conferences, livestream promotions, training, recruitment, advertisements, sponsorships, and equivalent non-industry-news content before selection.
- Company-announcement subjects must be no more than six Chinese characters. The body begins with the most material fact and figures, prefers verbatim 巨潮/issuer wording, and may use only minimal neutral connectors to join source fragments into a grammatical sentence; never replace the official text with an invented summary.
- Policy pages must follow the case table's native fonts, fills, column widths, row heights, page numbering, and source-bar gap. Remove unused blank rows. For standalone government-policy lists, exclude all `公开征求意见`、`征求意见稿`、意见征集 or consultation-only notices unless the user explicitly asks for drafts; report a shortfall instead of replacing them with weaker items.
- In Excel evidence sheets, the purple cell borders are the enclosure. Keep each left and right screenshot at natural aspect ratio and size; move or resize the purple frame/separator independently so each image's bottom is flush with its own frame. Never resize, stretch, pad, mask, or add thin image strips to make an image fit, and never move only one side of a shared separator. Never stitch multiple screenshots or page regions into one bitmap. When an item needs two or more source images, insert them as separate picture objects with a visible gap and verified non-overlapping anchors.
- Show the direct official URL as visible text and as the hyperlink in the same cell. Source screenshots must include the source identity and the exact passage used, with no unrelated lower-page material or large blank canvas.

## Stage Router

- `华鑫医药团队近期研究成果` + worksheet 1: Research Results.
- `近期行业重要政策` + `P22行业政策`: Industry Policy.
- both `近期行业要闻梳理` slides + `P23-24行业新闻`: Industry News.
- both `周重要上市公司公告一览` slides + `P25-26公司公告`: Company Announcements.

For a partial refresh, update only the named stage and preserve all other stages exactly.

## Delivery

Deliver one final PPTX/XLSX pair plus `weekly_run_manifest.json` and any validation/deviation records. Report each stage status, the selected weekly window, final item counts, and every blocked gate with its exact access or source reason.

## Bundled Scripts

- `preflight_weekly_report.py`: validate the pair and create the shared manifest.
- `extract_wechat_reports.py`: normalize an authorized 医药新观 feed/export.
- `select_weekly_pharma_policies.py`: filter and rank policy candidates only.
- `prepare_weekly_medalpha_news.py`: filter and rank the currently available verified 医药魔方Info candidates without engagement metrics; it reports content shortfall and evidence status separately.
- `tight_crop_wechat_screenshot.py`: crop WeChat evidence images.
- `select_weekly_pharma_announcements.py`: filter and rank announcement candidates only.
- `validate_excel_left_row_text.py`: compare final PPT rows with Excel left evidence crops.

Run a script with `--help` before first use. Selection scripts may reject or rank candidates; they must never rewrite copied source text.
