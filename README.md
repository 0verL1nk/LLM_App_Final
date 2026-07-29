# PaperSage

PaperSage 是一个面向论文阅读、证据检索与多 Agent 研究协作的项目式工作台。前端采用独立的 Vite React 应用，FastAPI 提供稳定的 HTTP 边界；文档上传、OCR、Embedding、长期记忆整理均在后台执行，不阻塞会话创建。

## 核心能力

- 项目工作台：资料、会话、证据与研究活动统一归属项目。
- Supervisor/Subagent：Leader 可并行委派 researcher、reviewer、writer，并依据真实 tool call 展示执行状态。
- 项目级 RAG：完整文档切分后写入 LanceDB，原生 Dense + FTS + RRF 混合召回；找相关资料先从全项目证据检索，不把文件目录注入提示词。
- 异步文档处理：上传后自动提取、OCR、Embedding 和版本发布，前端立即显示每份文件的真实阶段与进度。
- 长期记忆与会话命名：每轮结束后异步调用模型整理项目记忆；首个有效回答会异步生成会话标题，不覆盖手动命名。
- 持久会话：SQLite 保存项目、消息、设置与 ingestion 状态，LangGraph checkpoint 保存 Agent 状态。

## 技术栈

前端位于 `web/`：Vite、React、TypeScript、Tailwind CSS、shadcn/ui、Radix UI、TanStack Query、TanStack Router、Zustand、React Hook Form、Zod、Lucide React。

后端位于 `api/` 与 `agent/`：FastAPI、LangChain/LangGraph、Deep Agents、SQLite、LanceDB、FastEmbed、RapidOCR、RQ/Redis。

## 本地开发

要求 Python 3.11+、uv、Node.js 22+ 与 npm。

```bash
make install-dev      # 安装 Python 依赖
make web-install      # 按 package-lock 安装前端依赖
make run              # 一键启动 API :8000 与 Vite :5173
```

也可以分别启动：

```bash
make api-dev
make web-dev
```

生产构建与运行：

```bash
make web-build
make serve            # FastAPI 在 :8000 托管 web/dist
```

## 目录结构

```text
api/                    # HTTP transport、schema 与路由
web/src/
  components/ui/        # shadcn/ui 源码组件
  components/           # 应用壳与领域 UI
  pages/                # 路由页面
  lib/                  # API、Zod schema、Query hooks
  stores/               # Zustand UI 状态
agent/
  domain/               # 领域模型与契约
  application/          # 用例编排
  adapters/             # SQLite、LanceDB、文件与模型适配
  subagent/             # 子 Agent 定义
tests/                  # Python unit / integration / eval
docs/architecture/      # 架构决策与边界
```

## 质量门禁

```bash
make web-lint
make web-typecheck
make web-test
make web-build
make test-all
make quality-full
```

## 配置

复制 `.env.example` 并在 Web 设置页保存用户级 API Key、模型名称和兼容 Base URL。密钥只由后端读取，API 不返回完整值。

主要运行时变量：

```bash
AGENT_LANCEDB_DIR=./.cache/lancedb
LOCAL_RAG_PROJECT_MAX_CHARS=0
LOCAL_RAG_PROJECT_MAX_CHUNKS=0
RAG_INDEX_BATCH_SIZE=256
DOC_PARSE_BACKEND=auto
```

完整 Web 架构与 API 契约见 [docs/architecture/web-application.md](docs/architecture/web-application.md)。
## 桌面端发布

桌面版把 Vite 前端和 FastAPI 服务一起打包；窗口采用应用内自定义标题栏。开发时执行 `make desktop-dev`，本机构建执行 `make desktop-package-win`、`make desktop-package-mac` 或 `make desktop-package-linux`；产物在 `web/release/`。首次构建会收集 OCR 和本地检索依赖，耗时较长。

推送 `v*` tag 会触发 GitHub Actions 在 Windows、macOS 与 Linux runner 分别构建 NSIS、DMG、AppImage/deb，并统一作为 GitHub Release 附件发布；PR 则只验证前端、Electron 入口与服务资源边界。

正式公开发布前须配置代码签名与 macOS 公证密钥；详见 [桌面发布运维说明](docs/architecture/desktop-release.md)。

公开 Release 同时附带免费 GitHub/Sigstore 构建证明和 `SHA256SUMS.txt`，用于验证安装包来源与完整性。
