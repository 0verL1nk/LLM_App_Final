<p align="center">
  <img src="web/public/papersage-mark.svg" width="72" alt="PaperSage logo" />
</p>

<h1 align="center">PaperSage</h1>

<p align="center">面向本地资料的可追溯 AI 研究工作台。</p>

<p align="center">
  <a href="https://github.com/0verL1nk/PaperSage/actions/workflows/quality.yml"><img src="https://github.com/0verL1nk/PaperSage/actions/workflows/quality.yml/badge.svg" alt="Quality Gate" /></a>
  <a href="https://github.com/0verL1nk/PaperSage/releases"><img src="https://img.shields.io/github/v/release/0verL1nk/PaperSage?display_name=tag" alt="Release" /></a>
  <a href="https://pypi.org/project/paper-sage/"><img src="https://img.shields.io/pypi/v/paper-sage.svg" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
</p>

![PaperSage 系统能力总览](images/main.jpg)

PaperSage 把资料库、研究会话和引用证据放在同一个项目里。导入自己的文档后，可以立刻开始提问；解析、OCR 和索引在后台完成。每个结论都应能回到对应资料的页面和位置核对，而不只是得到一段聊天回答。

## 从资料到结论

1. **导入资料**：一次上传 PDF、DOCX、PPTX、XLSX、图片或 TXT。文件会异步经历转换、OCR、分块和完整索引，不阻塞新会话。
2. **发起研究**：在主会话中提问，或从当前讨论创建探索分支。系统从已就绪的项目资料中检索相关内容，并可按任务委派研究、审阅或写作角色。
3. **核对证据**：回答中的引用可以打开原始文档。对已 OCR 的页面，PaperSage 会根据保存的页码、坐标和置信度定位证据位置。

| 你会用到的能力 | PaperSage 如何实现 |
| --- | --- |
| 不被上传过程打断 | 资料处理是异步的；索引未完成时仍可开始会话，完成后自动进入检索范围。 |
| 回答可复查 | LanceDB 的向量与全文混合检索只使用完整发布的文档版本；候选检索和最终引用分开呈现。 |
| 研究可以延续 | 项目保存会话、分支、资料范围和长期记忆；运行事件与流式回复支持离开后重新进入。 |
| 复杂任务有分工 | Leader 仅在当前请求内调用 researcher、reviewer、writer 等子代理；它们不是脱离当前会话的后台任务。 |

## 30 秒开始

### 使用桌面版

从 [Releases](https://github.com/0verL1nk/PaperSage/releases) 下载 Windows、macOS 或 Linux 安装包。桌面版复用同一套 Web 界面，内置本地 API、文件能力、诊断日志与更新机制。

### 从源码运行

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 22+ 和 pnpm 11+：

```bash
corepack enable
make install-dev
make web-install
make run
```

然后打开 `http://127.0.0.1:5173`。`make run` 会同时启动 FastAPI（`:8000`）和 Vite 开发服务器（`:5173`）。

生产式本地运行：

```bash
make web-build
make serve
```

此模式由 FastAPI 在 `http://127.0.0.1:8000` 托管已构建的前端。

### 使用 PyPI 包

发布版本将 Web bundle 一并包含在 `paper-sage` wheel 中：

```bash
pip install paper-sage
paper-sage
```

这会启动本机服务；随后访问 `http://127.0.0.1:8000`，不会额外启动 Vite。

## 文档、模型与数据

- **文档处理**：PDF、图片和 TXT 会转换为可检索页面；Word、PowerPoint 与 Excel 会先使用本机 Microsoft Office，或 LibreOffice 后备方案转换为 PDF，再进入 PaddleOCR 流程。
- **证据定位**：OCR 保存页码、文本多边形和置信度。跨页段落或表格可以保留多个页面位置，供预览和高亮使用。
- **本地优先**：项目、会话和资料索引默认保存在本机的 SQLite 与 LanceDB 中。OCR 模型首次使用时下载到本地缓存，不预置到安装包。
- **模型与联网**：回答模型由你在设置或 `.env` 中配置；若启用 Web 搜索，查询会发送到所选搜索服务。请根据你的模型与搜索服务政策处理敏感资料。

从 [.env.example](.env.example) 复制配置模板。不要提交 API Key、签名证书或其他凭据。

## 工作方式

```mermaid
flowchart LR
  A[导入资料] --> B[转换与 OCR]
  B --> C[分块与索引]
  C --> D[混合检索]
  D --> E[带引用的回答]
  E --> F[打开原文并定位]
```

前端使用 Vite、React、TypeScript、Tailwind、shadcn/ui、Radix 和 TanStack；FastAPI 提供 API 边界。SQLite 保存项目与会话，LanceDB 保存项目级索引，Agent 状态和运行事件用于恢复研究过程。详见：[Web 架构](docs/architecture/web-application.md)、[Agent 运行时](docs/architecture/agent-runtime.md)、[桌面端](docs/architecture/desktop-application.md)。

## 开发

```bash
make check          # 快速质量门禁
make ci             # 完整离线 CI
make test-unit      # Python 单元测试
make web-test       # 前端测试
make desktop-dev    # Electron 开发壳
```

目录边界与质量要求见 [AGENTS.md](AGENTS.md)。提交使用 Conventional Commits：`feat:` 触发 minor，`fix:` 触发 patch，`!` 或 `BREAKING CHANGE:` 触发 major。Release Please 负责版本 PR；在仓库启用 Auto-merge 后，该版本 PR 会按规则自动合并，随后由 `vX.Y.Z` tag 触发统一的桌面端与 PyPI 发布流程。

## 贡献与安全

PR 请说明问题、变更范围、风险、回滚方式及验证命令。安全问题请遵循 [SECURITY.md](SECURITY.md) 私密报告，而不要直接公开提交凭据或漏洞细节。

## License

[MIT](LICENSE)
