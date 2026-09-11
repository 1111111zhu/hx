# Industry News Rules

## Source and Time

- Use only direct, openable original WeChat articles whose visible account identity is exactly `医药魔方Info`.
- Accept both `https://mp.weixin.qq.com/s?...` and `https://mp.weixin.qq.com/s/<article-id>` forms.
- Filter by the actual publication time in Beijing time. Do not substitute an event date, drafting date, or date mentioned inside the article.
- With an anchor date, use the most recently completed Saturday-through-Friday window. With an explicit start/end range, follow the user's range.
- Verify items independently. A failed item is rejected without rolling back other verified items.

## Hard Exclusions

Reject posts whose purpose is an activity, invitation, registration, agenda, schedule, ticket sale, attendance notice, conference, congress, summit, forum, salon, seminar, exhibition, exhibitor or sponsor recruitment, livestream preview/reservation, countdown, training course/camp, recruitment, advertisement, investment promotion, sponsorship, or equivalent promotion.

Strong rejection signals include `邀请函`、`诚邀`、`报名`、`议程`、`日程`、`门票`、`购票`、`扫码`、`参会`、`招商`、`招展`、`赞助`、`直播预告`、`直播预约`、`开播预告`、`倒计时`、`培训班`、`训练营`、`招聘`、`招募`、`广告`.

Do not reject a factual news report merely because it says an event occurred. Reject it when the title or opening content is promotional, participation-oriented, or recruitment-oriented. A promotional post remains excluded even if it mentions an important medical fact.

## Text Extraction

- Capture the complete topmost substantive paragraph from the original article.
- Store an untouched canonical copy of that paragraph.
- Preserve wording, punctuation, figures, names, dates, and qualifiers exactly in the canonical source field.
- Do not use an aggregator abstract, headline, editor's note, image caption, recommendation block, or a later paragraph as a substitute.
- Do not summarize, shorten, reorder, add a lead sentence, prepend the headline, or add a reporting date.
- For PPT rows, split the topmost paragraph into two display fields: the date column uses the date stated in that first paragraph, not the WeChat/article publication date; the body column must not add a date prefix. If the paragraph begins with that date marker, remove only that leading marker from the PPT body and keep the remaining wording unchanged. Other substantive dates inside the paragraph remain untouched. If the first paragraph has no explicit date, stop and ask rather than substituting the article publication date.
- Visual line wrapping is formatting and must not alter stored text.

## Ranking and Count

- Target 10 qualified in-window items.
- Rank the comparison set by: `事件重要性` → `产业影响` → `信息稀缺性` → `发布时间`.
- Suggested deterministic scoring is 25 points for event importance, 10 for industry impact, and 5 for information scarcity; use publication time only as the final tie-breaker during selection.
- After selecting the strongest items, display them by publication time descending.
- Never request, estimate, record, score, or rank by reading count, likes, recommendations, shares, favorites, comments, or engagement rate.
- Do not add routine or promotional items merely to reach 10. If fewer than 10 qualify, report `content_shortfall` and the exact number missing. Clear unused old-week rows when editing an artifact; do not leave them looking current.

## Content and Evidence States

Treat content and evidence as separate state machines:

| State | Meaning | Required action |
|---|---|---|
| `completed_content` | Account, date, direct URL, and top paragraph are verified | Keep the selected content |
| `content_shortfall` | Fewer than 10 items passed | Keep verified items and report the gap |
| `evidence_pending` | Content is verified but its source crop is missing or failed QA | Keep content; retry or request only the missing evidence |
| `completed` | Content and requested evidence/artifact QA passed | Deliver as complete |
| `blocked_source` | No item can be verified from any usable original-source route | Report the exact access problem |

Never let missing engagement metrics change any state. Never let one missing screenshot revert the entire section.

## Evidence Rules

- Crop from the article top through the lower boundary of the complete first paragraph. Retain the title, `医药魔方Info`, publication time, and any required qualifying banner. Exclude later article text, recommendation/copyright blocks, action bars, and large blank canvas.
- Bind each selected item to its displayed text, direct URL, account identity, publication time, source paragraph, capture time, and evidence path/status.
- When two or more images are needed, insert them as separate picture objects. Never stitch screenshots or page regions into one bitmap.
- Keep at least 12 px visible spacing between images and verify pairwise non-intersection after saving and reopening the workbook.
- Missing evidence blocks only a claim of evidence-complete delivery; it does not discard verified content.

## Candidate Input Schema

The bundled selector accepts a JSON array or an object containing `items`, `records`, `data`, `results`, or `news`. It recognizes common field aliases:

- title: `title`, `headline`, `name`
- publication time: `published_at`, `publish_time`, `published`, `publishedAt`, `date`, `time`
- PPT first-paragraph date: `ppt_date`, `pptDate`, `first_paragraph_date`, `firstParagraphDate`, `event_date`
- URL: `url`, `link`, `href`, `article_url`, `articleUrl`, `source_url`, `sourceUrl`
- paragraph: `first_paragraph_raw`, `canonical_text`, `source_content`, `exact_excerpt`, `content`, `body`, `article_text`, `excerpt`
- source: `source`, `source_name`, `sourceName`, `publisher`, `media`
- optional evidence: `source_screenshot`, `evidence_path`, `screenshot`, `source_crop`

The source value must resolve to `医药魔方Info`. The selector output records the date window, requested count, selected count, shortfall, content status, evidence status, ranking method, exclusions, and selected items.

## Audit Checklist

For every selected item, verify:

1. The visible account is `医药魔方Info`.
2. The publication time is inside the requested window.
3. The direct URL opens the same original article.
4. The stored paragraph is the complete topmost original paragraph.
5. The item is factual industry news, not promotion.
6. No engagement metric affected acceptance or order.
7. Evidence status is recorded independently from content status.
