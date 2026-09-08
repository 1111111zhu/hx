# hx

华鑫医药工作流 Skills。

## Skills

### 华鑫医药行业新闻

目录：[huaxin-pharma-industry-news](huaxin-pharma-industry-news/)

安装包：[huaxin-pharma-industry-news.skill](huaxin-pharma-industry-news.skill)

用于筛选、核验和排序华鑫医药周报 P23-24 行业新闻。仅采用医药魔方Info原创文章，不使用阅读量等互动指标；排除活动、邀请、报名、直播推广和广告内容。内容完成状态与证据图片状态分别管理，多张证据图不得拼接或重叠。

调用示例：

```text
用 $huaxin-pharma-industry-news 筛选并核验本周医药魔方Info行业新闻。
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
