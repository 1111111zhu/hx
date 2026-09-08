# hx

华鑫医药工作流 Skills。

## Skills

### 华鑫医药周报更新（PPT + Excel）

目录：[huaxin-pharma-weekly-report](huaxin-pharma-weekly-report/)，安装包：[huaxin-pharma-weekly-report.skill](huaxin-pharma-weekly-report.skill)。包含研究、政策、新闻和公告规则、配对模板及检查脚本。

```text
用 $huaxin-pharma-weekly-report 按锚定日期 YYYY-MM-DD 更新行业新闻，交付配套 PPTX 和 XLSX。优先用我提供的模板，没有附件时用内置模板。
```

### 华鑫医药行业新闻

目录：[huaxin-pharma-industry-news](huaxin-pharma-industry-news/)

安装包：[huaxin-pharma-industry-news.skill](huaxin-pharma-industry-news.skill)

用于更新华鑫医药周报 P23-24 行业新闻，默认交付配套 PPTX + XLSX。包含完整历史版式模板与从来源核验到 PPT 原生表格、Excel 双侧证据、图片防重叠和保存后检查的流程。仅采用医药魔方Info原创文章，不使用阅读量；排除活动、邀请、广告等推广内容。JSON/Markdown 只作中间文件，明确要求仅清单时例外。

调用示例：

```text
用 $huaxin-pharma-industry-news 更新本周医药魔方Info行业新闻，使用附件或内置配对模板，交付可编辑 PPTX 和带证据图片的 XLSX。
```

详细流程见 [SKILL.md](huaxin-pharma-industry-news/SKILL.md)，完整规则见 [industry-news-rules.md](huaxin-pharma-industry-news/references/industry-news-rules.md)。该 Skill 已允许根据任务语义自动调用。

### 华鑫医药周报公众号素材包

目录：[huaxin-weekly-wechat-package](huaxin-weekly-wechat-package/)

安装包：[huaxin-weekly-wechat-package.skill](huaxin-weekly-wechat-package.skill)

用于把华鑫医药周报 PPTX 制作为公众号 Word 与图片素材包。

调用示例：

```text
用 $huaxin-weekly-wechat-package 生成这份周报的 Word 和素材包。
```

详细流程见 [SKILL.md](huaxin-weekly-wechat-package/SKILL.md)，用户规则见 [规则.md](huaxin-weekly-wechat-package/references/规则.md)。

## 安装

将所需 Skill 文件夹复制到 Codex 的个人 skills 目录，或使用仓库内对应的 `.skill` 安装包。

其他支持 SKILL.md 的智能体可安装完整目录；不支持自动发现的智能体需显式读取对应 SKILL.md。直接打开本仓库可从 [AGENTS.md](AGENTS.md) 找到任务入口。两个更新 Skill 各自包含模板，无需同时安装。安装包是 ZIP 格式，可解压使用。

模板取自图二所示 20260829–20260904 配对版，仅用于版式，历史新闻不是本周成果。新附件优先。完整执行还需要源网页访问、文件编辑与渲染能力；Skill 不携带登录会话。结构验证不能代替真实来源和逐页视觉检查。
