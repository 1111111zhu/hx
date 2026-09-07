# hx

华鑫医药周报公众号 Word 与图片素材包制作 skill。

## 使用

将 `huaxin-weekly-wechat-package` 文件夹放入 Codex 的个人 skills 目录，也可使用仓库内的 `.skill` 打包文件。

提供周报 PPTX 后调用：

```text
用 $huaxin-weekly-wechat-package 生成这份周报的 Word 和素材包。
```

输出包含 `文字.docx`、合规说明图、全部报告页 PNG 和 ZIP 素材包。

## 固定规则

- 合规说明文字整体居中，首行距上边框与末行距下边框留白相等。
- Word 末尾保留报告链接和联系人胡博新；无链接时留空，正常生成与交付。
- 保留所有原报告页，报告图片通过 PowerPoint 放映截图制作。
- 仅制作本地材料，不包含公众号上传或发布操作。

详细流程见 [SKILL.md](huaxin-weekly-wechat-package/SKILL.md)，用户规则见 [规则.md](huaxin-weekly-wechat-package/references/规则.md)。

## 环境

此流程面向 macOS 和 Microsoft PowerPoint，需要可用的电脑控制接口，以及 Word 创建、后台渲染与图片检查工具。合规模板已包含在 skill 的 assets 目录中。
