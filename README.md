# hx

华鑫医药工作流 Skills。

## 功能总览

这个仓库按三个主要功能维护；日常使用优先从下表选择入口。

| 功能 | 对应目录 | 安装包 | 用途边界 |
| --- | --- | --- | --- |
| 周报制作 | [`huaxin-pharma-weekly-report/`](huaxin-pharma-weekly-report/) | [`huaxin-pharma-weekly-report.skill`](huaxin-pharma-weekly-report.skill) | 更新华鑫医药周报 PPTX/XLSX，包括研究成果、行业政策、行业新闻、公司公告及 Excel 证据截图。 |
| 周报公众号发布素材 | [`huaxin-weekly-wechat-package/`](huaxin-weekly-wechat-package/) | [`huaxin-weekly-wechat-package.skill`](huaxin-weekly-wechat-package.skill) | 将已完成的周报 PPTX 制作为公众号 Word 文案和图片素材包；不负责更新周报内容。 |
| 通用文章公众号发布 | [`通用文章外发/`](通用文章外发/) | [`通用文章外发.skill`](通用文章外发.skill) | 将研究报告 Word 制作为微信公众号正文、首图和可选草稿；不用于周报 PPT/XLSX 更新。 |

`huaxin-pharma-industry-news/` 是周报制作中“行业新闻”阶段的专项/兼容包，保留给只更新 P23-24 行业新闻的场景；完整周报制作仍以 `huaxin-pharma-weekly-report/` 为主入口。

## Skills

### 功能一：华鑫医药周报制作（PPT + Excel）

目录：[huaxin-pharma-weekly-report](huaxin-pharma-weekly-report/)，安装包：[huaxin-pharma-weekly-report.skill](huaxin-pharma-weekly-report.skill)。包含研究、政策、新闻和公告规则、配对模板及检查脚本。

```text
用 $huaxin-pharma-weekly-report 按锚定日期 YYYY-MM-DD 更新行业新闻，交付配套 PPTX 和 XLSX。优先用我提供的模板，没有附件时用内置模板。
```

最新规则备注：

- 行业政策和公司公告先按影响力/重要性筛选，入选后再按发布时间倒序展示。
- 行业政策、公司公告正文必须来自官方原文件或详情页原文；可加入少量中性连接词，但连接词需单独记录。
- Excel 证据截图必须覆盖正文所用原文片段；跨页或不连续内容分成独立截图，不拼接、不重叠。
- 公司公告按“业绩/临床进展 → 重大获批/交易/控制变更 → 重大风险/资本事项 → 其他重要事项”排序；PPT `公告主题` 必须恰好四个汉字。
- 不使用“业绩快报”作 PPT 主题；业绩预告用于正式结果前的预计区间或盈亏预警，业绩公告用于已披露实际营收、归母净利等结果。

### 华鑫医药行业新闻

目录：[huaxin-pharma-industry-news](huaxin-pharma-industry-news/)

安装包：[huaxin-pharma-industry-news.skill](huaxin-pharma-industry-news.skill)

用于更新华鑫医药周报 P23-24 行业新闻，默认交付配套 PPTX + XLSX。包含完整历史版式模板与从来源核验到 PPT 原生表格、Excel 双侧证据、图片防重叠和保存后检查的流程。仅采用医药魔方Info原创文章，不使用阅读量；排除活动、邀请、广告等推广内容。JSON/Markdown 只作中间文件，明确要求仅清单时例外。

调用示例：

```text
用 $huaxin-pharma-industry-news 更新本周医药魔方Info行业新闻，使用附件或内置配对模板，交付可编辑 PPTX 和带证据图片的 XLSX。
```

详细流程见 [SKILL.md](huaxin-pharma-industry-news/SKILL.md)，完整规则见 [industry-news-rules.md](huaxin-pharma-industry-news/references/industry-news-rules.md)。该 Skill 已允许根据任务语义自动调用。

### 功能二：华鑫医药周报公众号素材包

目录：[huaxin-weekly-wechat-package](huaxin-weekly-wechat-package/)

安装包：[huaxin-weekly-wechat-package.skill](huaxin-weekly-wechat-package.skill)

用于把华鑫医药周报 PPTX 制作为公众号 Word 与图片素材包。

调用示例：

```text
用 $huaxin-weekly-wechat-package 生成这份周报的 Word 和素材包。
```

详细流程见 [SKILL.md](huaxin-weekly-wechat-package/SKILL.md)，用户规则见 [规则.md](huaxin-weekly-wechat-package/references/规则.md)。

### 功能三：通用文章公众号发布

目录：[通用文章外发](通用文章外发/)，安装包：[通用文章外发.skill](通用文章外发.skill)。

用于将华鑫证券研究报告 Word 按固定规则制作成公众号首图和正文；配置使用者自己的公众号 API 后，可上传素材并创建草稿，但不提供发布命令。

首次在本机配置 API：

```text
cd 通用文章外发
sh scripts/setup_local_api.sh
```

真实 AppID、AppSecret、access token 和账号密码不进入仓库；每个使用者单独配置自己的账号和 IP 白名单。

## 安装

将所需 Skill 文件夹复制到 Codex 的个人 skills 目录，或使用仓库内对应的 `.skill` 安装包。

其他支持 SKILL.md 的智能体可安装完整目录；不支持自动发现的智能体需显式读取对应 SKILL.md。直接打开本仓库可从 [AGENTS.md](AGENTS.md) 找到任务入口。两个更新 Skill 各自包含模板，无需同时安装。安装包是 ZIP 格式，可解压使用。

模板取自图二所示 20260829–20260904 配对版，仅用于版式，历史新闻不是本周成果。新附件优先。完整执行还需要源网页访问、文件编辑与渲染能力；Skill 不携带登录会话。结构验证不能代替真实来源和逐页视觉检查。
