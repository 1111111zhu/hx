# 华鑫医药工作台

本地网页控制台，把仓库里三个 skill 框架包成可一键启动的卡片，并集中管理两个 API 槽位。

- 纯 **Python 3 标准库**（`http.server.ThreadingHTTPServer` + 手写路由），零第三方依赖。
- 前端 HTML/CSS/JS 全部本地文件，**无 CDN、无外链字体或图标**，断网也能正常显示。
- 只监听 `127.0.0.1`，不对外暴露。

---

## 一键启动

双击 **`workbench/启动工作台.command`**（已 `chmod 755`）。它会依次：

1. 启动本地服务，端口从 `8765` 起，**被占用时自动顺延**；
2. 等真实端口就绪后，自动打开浏览器到 `http://127.0.0.1:<真实端口>/`；
3. 检查 `dsh` 是否可用并打印版本；
4. 检查微信公众号 API 状态，**未配置就自动拉起配置终端**；
5. 前台驻留，直到你按 `Ctrl+C`。

也可以手动启动：

```sh
python3 workbench/server.py            # 默认 8765，占用则顺延
python3 workbench/server.py --port 9000 --open
```

服务启动时会打印清晰的服务 URL。

### 环境变量（都可选）

| 变量 | 作用 |
|---|---|
| `PYTHON_BIN` | 指定 python3 解释器，默认 `python3` |
| `DSH_BIN` | 指定 dsh 路径，默认 `/opt/homebrew/bin/dsh` |
| `WORKBENCH_BOOT_DSH` | 控制启动时是否额外在新终端开一个 dsh 会话。默认 `auto`：**没有** dsh 在跑就拉起，检测到 `DSH_WEB_URL`（默认 `http://127.0.0.1:3080`）上已有 dsh 就跳过以免抢端口。设 `1` 强制拉起，设 `0` 完全跳过。 |
| `DSH_WEB_URL` | `auto` 用来判断"是否已有 dsh 在运行"的地址，默认 `http://127.0.0.1:3080` |
| `WORKBENCH_DSH_CMD` | 覆盖卡片启动所用的命令（调试用） |

---

## 三个框架分别做什么

| 卡片 | 目录 | 入口 | 产出 |
|---|---|---|---|
| **周报制作** | `周报制作/` | `周报制作/SKILL.md` | 一套校验过的 **PPTX + XLSX 配对文件**。JSON / Markdown 只是中间记录，不是交付物。只更新行业新闻时可改读 `周报制作/行业新闻专项包/SKILL.md`。 |
| **周报公众号发布** | `周报公众号发布/` | `周报公众号发布/SKILL.md` | 一个按报告日期命名的文件夹，内含 `文字.docx`、`01_合规说明.png`、以及全部报告页 PNG。**不含**公众号上传或发布。 |
| **通用文章公众号发布** | `通用文章公众号发布/` | `通用文章公众号发布/SKILL.md` | 研究报告 Word → 合规首图 + 正文 HTML；默认把 `正文.html` 放桌面。配置好凭证后可保存公众号**草稿**（不能发布）。 |

### 卡片怎么跑起来

点「启动」后，后端在**仓库根目录**以子进程方式执行一次 one-shot 任务：

```sh
dsh --profile headless "<提示词>"
```

提示词默认引用对应 skill 的 SKILL.md 路径，例如周报制作卡片是：

```text
先读取 周报制作/SKILL.md，再执行周报更新：按该 skill 的输入契约刷新配对交付的 PPTX 与 XLSX。
```

每张卡片的提示词输入框都可以**直接改**（加上你的 PPTX/Word 附件、日期、范围等），改完再点启动。
子进程的 stdout/stderr 会实时写入日志，页面用轮询 `GET /api/runs/<id>?offset=N` 增量回显，请求不会阻塞。

> 若 `dsh` 不存在或 profile 不存在，卡片会显示明确的红色错误提示（而不是白屏），
> 并把真实命令与退出码记进运行日志。可在页面「运行环境」里改 dsh 路径与 profile。

> **已验证**：`dsh --profile headless "<提示词>"` 是真实可用的命令。本机 `~/.dsh/profiles/`
> 下确实存在 `headless` profile（bundle 为 `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-headless`）。
> 唯一的前置条件是 DeepSeek 凭证——见上一节。

> **已知限制**：`dsh` 每次启动都会重写 `$DSH_HOME/profiles/<profile>/cordis.yml` 来重新组合
> profile 树。如果 `~/.dsh` 不可写（例如运行在受限沙箱里），dsh 会以
> `EPERM: operation not permitted, open '.../cordis.yml'` 退出——工作台会如实把这段错误显示在运行日志里，
> 而不是假装成功。解决办法：给 `~/.dsh` 写权限，或把 `DSH_HOME` 指向一个可写目录。

---

## 两个 API 槽位怎么填

### 1. DeepSeek

工作台自己的配置，写入 `workbench/config.json`（**已被 `.gitignore` 忽略**）。

| 字段 | 默认值 |
|---|---|
| `base_url` | `https://api.deepseek.com` |
| `api_key` | 空 |
| `model` | `deepseek-chat` |

点「测试连接」会请求 `{base_url}/v1/models`（404 时回退 `/models`），把 HTTP 状态、
模型列表或具体错误（401/403 表示 key 无效、网络不可达等）回显在页面上。
密钥输入框是 `password` 类型；重新载入页面时只回显**后 4 位**（形如 `••••••••abcd`），
留空提交表示不修改已保存的值（防止页面刷新后误清空）。

要**移除**已保存的 key，用「清除密钥」按钮：它会提交 `{"deepseek":{"clear_api_key":true}}`，
把 `api_key` 置空并刷新状态徽章。空字符串和这个显式标志是两种不同语义，不要混用。

`config.json` 落盘权限为 `600`，且已被 `.gitignore` 忽略；不要把真实 key 提交到 GitHub。

#### 这个 key 也会传给 dsh

`dsh` 的 headless profile 从环境变量读取 provider 凭证，缺失时会直接报：

```text
dsh: MISSING_CREDENTIAL: llm-deepseek: no API key for provider route "deepseek-official"
```

所以启动卡片时，工作台会把这里配好的值**注入子进程环境**（不覆盖你已有的同名变量），
并在运行日志头部打印 `[注入环境变量] DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL`：

| 工作台字段 | 注入的环境变量 |
|---|---|
| `deepseek.api_key` | `DEEPSEEK_API_KEY` |
| `deepseek.base_url` | `DEEPSEEK_BASE_URL` |

如果你更希望自己在 shell 里 `export DEEPSEEK_API_KEY=...`，那也可以——已存在的环境变量优先，
工作台不会覆盖它。

### 2. 微信公众号

**工作台不存储、不接收、不显示 AppID / AppSecret。** 这个槽位完全复用仓库既成的凭证机制：

- 脚本：`通用文章公众号发布/scripts/wechat_draft_api.py`
- 凭证存放：**macOS 钥匙串**，`service = codex-wechat-article`，
  `account = WECHAT_OFFICIAL_APP_ID` / `WECHAT_OFFICIAL_APP_SECRET`；
  钥匙串取不到时回退读**同名环境变量**。
- 配置入口：`通用文章公众号发布/scripts/setup_local_api.sh`（内部依次跑 `configure` + `check-auth`）
- 文档：`通用文章公众号发布/references/api-architecture.md`

页面上的操作只有两个：

- **打开配置终端** — 调 `open -a Terminal <setup_local_api.sh>`，在**你自己的终端里**交互输入密钥。
  工作台只是把窗口拉起来，密钥不会经过 HTTP，也不会落进 `config.json`。
- **刷新状态** — 运行 `python3 通用文章公众号发布/scripts/wechat_draft_api.py check-auth`，
  按退出码和脚本输出判定状态：

  | 徽章 | 含义 |
  |---|---|
  | 待配置 | 还没检查过 |
  | 未配置 | 钥匙串和环境变量里都找不到 `WECHAT_OFFICIAL_APP_ID` / `_SECRET` |
  | 已连接 | `check-auth` 通过，已取得 access_token（**不显示 token 值**） |
  | 连接失败 | 其他错误，附微信返回的 `errcode` + `errmsg` |

> 微信公众号 API 要求把调用方的公网出口 IP 加入白名单，否则会返回 `errcode 40164` 一类的错误。

---

## 产出物在哪

- **周报制作**：用户指定的配对 PPTX/XLSX 位置；未指定时用 `周报制作/assets/templates/` 里的内置模板
  （内置模板含历史内容，不等于"已更新成功"）。
- **周报公众号发布**：按报告日期命名的文件夹（如 `9月20日医药周报/`），
  内含 `文字.docx` + `01_合规说明.png` + `02_第01页.png` … 全部报告页 PNG。
- **通用文章公众号发布**：默认 `正文.html` 放**桌面**，PNG 素材与说明放工作目录；
  保存草稿时草稿出现在公众号后台「草稿箱」。
- **工作台自身**：运行记录在 `workbench/runs/`（`<id>.json` 元信息 + `<id>.log` 完整输出），已被 git 忽略。

---

## 如何停止服务

- 双击启动的那个**终端窗口里按 `Ctrl+C`**（推荐）。
- 或结束进程：`pkill -f "workbench/server.py"`。

服务退出时会自动删除 `workbench/runs/server.port`。

---

## HTTP 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 控制台页面（`index.html`） |
| GET | `/api/frameworks` | 三个框架元信息：显示名、相对路径、SKILL.md 摘出的简介、目录最近修改时间、dsh 可用性 |
| GET | `/api/config` | 读配置（DeepSeek key 打码；微信只回状态与脚本位置） |
| POST | `/api/config` | 写配置（打码值/空值表示不修改；微信字段一律丢弃） |
| POST | `/api/test-deepseek` | 测试 DeepSeek 连通性 |
| GET | `/api/wechat/status` | 微信槽位已记录的状态（不发网络请求） |
| POST | `/api/wechat/check` | 运行 `check-auth`，返回 status / errcode / errmsg |
| POST | `/api/wechat/configure` | 在终端里拉起 `setup_local_api.sh` |
| GET | `/api/dsh` | dsh 探测结果（路径、版本、可用 profile） |
| POST | `/api/run` | 启动一次框架任务，返回 run id |
| GET | `/api/runs` | 运行记录列表 |
| GET | `/api/runs/<id>?offset=N` | 单次运行的状态 + 从第 N 个字符起的增量输出 |
| GET | `/api/skill/<key>` | 以只读页面查看对应 `SKILL.md` |

## 文件清单

```
workbench/
├── 启动工作台.command   # 双击启动（755）
├── server.py            # 全部后端逻辑
├── index.html           # 控制台页面
├── styles.css           # 手写样式
├── app.js               # 原生 JS，无依赖
├── config.example.json  # 占位示例（可提交）
├── README.md            # 本文件
└── runs/                # 运行时产物（git 忽略）
```
