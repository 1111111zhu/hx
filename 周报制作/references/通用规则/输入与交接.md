# Input and Handoff Contract

This workflow is not portable as a chat transcript alone. A forwarded request is ready only when the receiver has the same executable skill and the task-specific files, sources, access, and decisions listed below.

## Minimum Transfer Package

1. **Skill bundle**: the complete `huaxin-pharma-weekly-report` directory or its ZIP, including `SKILL.md`, `references/`, and `scripts/`.
2. **Baseline pair**: prefer the latest user-supplied `.pptx` and matched `.xlsx`. If none is attached, use this bundle's `assets/templates/weekly-template.pptx` and `evidence-template.xlsx` as the historical layout baseline. This pair matches the user's illustrated output, but its old news must be replaced. Do not require a fresh attachment when the bundled pair is sufficient. Exclude `~$` lock files.
3. **Anchor date and scope**: one `YYYY-MM-DD` anchor date and either `all stages` or an explicit list of stages to update.
4. **Source/access package** for every requested stage:
   - Research: a user-authorized 医药新观 WeWe-RSS/feed/export or normalized export file.
   - Policy: internet access to original national government/regulator detail pages or files.
   - Industry news: either source access that can discover 医药魔方Info articles or any available in-window candidate records. Each selected item needs a direct original article URL, verified account identity, publication time, and its original topmost paragraph. Source screenshots may be captured after content selection. Reading counts and interactions are not required. A browser login/session is task-local and must not be assumed to transfer.
   - Company announcements: access to 巨潮资讯网/同花顺 and HKEX or issuer-original disclosures, including final direct detail/attachment URLs.
5. **Special decisions**: state whether `公司公告以半年报为主` is required and identify any explicit gate override. Silence means normal impact-first selection and no override.

The approved baseline pair itself is the visual example. Do not replace it with a verbal description of colors, row heights, or page structure.

## User-Confirmed Rules to Preserve on Handoff

- Compare every edited PPT page to the case for font family, size, weight, alignment, table geometry, row heights, page number, footer/source-bar gap, and blank rows.
- Industry news: use the 医药魔方Info article's topmost original paragraph verbatim; do not add an opening sentence, headline, or extra date to the overview body. Crop the source image only through that paragraph's lower black line, including the line and everything above it. Do not use reading or interaction metrics. Rank by event importance, industry impact, information scarcity, and publication time, after excluding activities, invitations, registrations, conferences, livestream promotions, training, recruitment, advertisements, and sponsorship content.
- Company announcements: the PPT `公告主题` is exactly four Chinese characters and must not use `业绩快报`. Use `业绩预告` for forecast/alert filings before actual results, and `业绩公告` for disclosed actual revenue/net-profit results, including material results filings whose original title says `业绩快报`. Use exact original filing text selected by deletion; minimal neutral connectors are allowed only when logged separately and when they add no fact or interpretation.
- Policy/government announcements: use direct national official URLs, match the case policy-table style, remove blank rows, and exclude `公开征求意见`/`征求意见稿`/意见征集 notices unless drafts were explicitly requested.
- Policy and company-announcement selection is materiality-first, not date-first. Policy materiality is bounded by national reach, binding/implementation force, effect on payment/procurement/market access/regulatory rules, affected population or industry breadth, and practical magnitude. Company announcements place material earnings and material clinical progress in the top tier.
- For policy and company announcements, every substantive fragment in the displayed body is exact extractive text from the original official file/page. Minimal logged neutral connectors need not appear in evidence. Every source fragment must be legible in the matching right-side Excel screenshot(s); use separate images for non-contiguous regions or pages, never stitch them, and require pairwise non-overlap after reopening the workbook.
- Excel evidence: preserve each screenshot's natural size/aspect ratio and move the purple frame/separator to the image boundary. Left and right bottoms align independently to their own purple frames; never stretch, pad, mask, or add thin image strips. Visible URL text and hyperlink target must share the same cell.

## Readiness Gate

Before editing, record the following in the manifest or run notes:

| Check | Pass condition | If missing |
|---|---|---|
| Skill available | All bundled references and scripts are readable | Stop the run; request the complete bundle |
| Pair unambiguous | One supplied matching pair, otherwise the bundled pair | Stop only if both routes are absent or supplied versions are ambiguous |
| Date fixed | Anchor date is explicit or reliably supplied by the active task | Do not guess a historical reporting week |
| Research feed | Authorized feed/export is readable | `blocked_source`; preserve research section |
| News source access | At least one usable route can discover or open 医药魔方Info originals | If no item can be verified, `blocked_source`; otherwise continue item by item |
| News content | Selected items have original URL, account identity, publication time, and topmost paragraph | Reject only the affected item; do not roll back other verified news |
| News source crops | Selected items have matching source crops | Mark affected evidence `evidence_pending`; do not discard or revert verified news content |
| Direct sources | Final direct pages/files open and match their records | Reject the affected item; preserve other verified items |

Do not weaken a gate because another agent previously claimed it had passed. Recheck against the files and access available in the current task.

## Standard Forwarding Prompt

Send the ZIP, the approved PPTX/XLSX pair, and the source package together with this text:

> 请先安装/读取附件中的 `huaxin-pharma-weekly-report` 完整技能包，再执行周报更新。锚定日期为 `YYYY-MM-DD`；更新范围为 `[全部 / 研究成果 / 行业政策 / 行业新闻 / 公司公告]`。以附件中的 PPTX/XLSX 配对文件为唯一内容基线和版式标准，原文件不得覆盖。先运行预检并报告周区间和各阶段输入是否齐全。行业新闻逐条核验账号、日期、直链和原文首段；单条不合格只淘汰该条，截图暂缺标记为 `evidence_pending`，不得因此回退已核验内容。行业新闻不要求阅读量，但必须排除活动、邀请、广告等非行业新闻。不得自行补写或用旧内容冒充已更新。最终交付 manifest，并仅把证据齐全且保存后复检通过的 PPTX/XLSX 标记为完整完成。

Replace the placeholders before sending. If the receiver cannot install or read the skill bundle, do not ask them to reproduce the work from the prompt alone.

## Common Causes of Poor Forwarded Results

- Only the conversation was forwarded; the local skill and scripts were not.
- The receiver received a PPTX without its matched evidence workbook, or vice versa.
- “Use the latest approved version” was stated without attaching that version.
- The reporting date or requested stage scope was omitted.
- Logged-in browser state, WeChat exports, reading metrics, or direct-source evidence was assumed to exist in another task.
- A blocked source was treated as permission to improvise.
- The output was not reopened, rendered, and compared with the saved workbook evidence.
