---
name: wechat-article-publisher
description: "将华鑫证券研究报告 Word 按固定公众号规则制作成首图、正文和可选公众号草稿。适用于公司报告、事件点评和行业研究等 Word 到微信公众号内容流程；不负责发布文章或迁移账号密码。"
---

# 通用文章外发

按本 Skill 处理“Word 研究报告 → 微信公众号正文”的任务。先读取 [规则](references/规则.md)；只有需要调用公众号 API 时才读取 [API 架构](references/api-architecture.md)。

## 结果

- 正文第一张图使用输入 Word 报告第一页的完整截图。
- 如果用户提供公众号封面/合规 PPT，按模板替换证券简称、股票代码、标题、日期、分析师和 SAC 编号，不改变整体紫色版式。
- 截图之后以原报告的“事件”“投资要点”“盈利预测”“风险提示”为主，保留原文数字、单位、评级和限定语，只清理页眉、页脚、断行和 Word 转换残留。
- 先生成本地可预览 HTML/Word 素材。没有 API 配置时，交付可复制粘贴的正文即可。

## 公众号 API 模式

仅在用户明确要求“保存草稿”并且完成配置后使用 `scripts/wechat_draft_api.py`：

1. `python scripts/wechat_draft_api.py configure`：在本机配置自己的 AppID 和 AppSecret。macOS 优先写入钥匙串；其他系统使用环境变量或系统密钥管理器。绝不把真实凭证写入仓库。
2. `python scripts/wechat_draft_api.py check-auth`：只读验证 access token 和接口权限。
3. 使用 `upload-thumb` 上传封面，再使用 `upload-image` 上传正文图片，替换正文 HTML 中的本地图片路径。
4. 只有用户确认保存草稿后，才运行 `create-draft`。脚本不包含发布命令，不能发布文章。

API 请求从使用者自己的本机或服务器发出，需由使用者将该出口公网 IP 加入公众号白名单。Skill 不共享创建者的账号、密码、AppSecret、Cookie 或登录状态。

## 安全边界

- 不迁移或上传公众号登录密码、AppSecret、access token、Cookie、二维码或验证码。
- 不把凭证放入 Skill、ZIP、GitHub、日志、示例文件或生成的 HTML。
- 不绕过 CAPTCHA、扫码、登录或浏览器安全策略。
- 不执行群发、发布、删除草稿、修改菜单或账号设置。
- 创建草稿、上传素材等外部写入动作必须在最后一步再次取得用户确认。

## 运行约束

- 需要输入 Word 时，使用 documents Skill 完成正文提取和第一页渲染检查；不要把整篇研究报告直接改写成营销稿。
- 需要处理 PPT 模板时，优先在副本上编辑并保留原文件；核对标题、日期、分析师和 SAC 编号。
- API 脚本使用 Python 标准库，不要求把第三方 SDK 或密钥提交到仓库。
- 任何无法核实的接口权限或素材限制都要报告，不用浏览器 Cookie 代替官方 API。
