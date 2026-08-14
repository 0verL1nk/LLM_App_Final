# Paper authoring workspace

## Why

当前“研究工作区”以 AI 对话流为页面主体，论文写作只能作为聊天结果的后续动作。
对用户而言，真正的主对象应是正在写的论文：需要同时看到可编辑的 LaTeX 源码、
可靠的编译产物和可回到证据的写作修改。AI 对话是协作入口，而不是取代论文的主
画布。

## What Changes

1. 每个项目可拥有可版本化的 `PaperDraft`；其 canonical source 是受控目录中的 LaTeX
   文件树，不能由浏览器直接伪造文件状态。
2. 新增“论文工作区”：桌面宽屏使用源码编辑器与已编译 PDF 的并排主画布；窄屏改为
   可切换的源码/PDF 视图。
3. 编译由后端受限 worker 执行，返回真实的 artifact、diagnostics 与 source mapping；
   UI 绝不显示假 PDF、假编译进度或示例诊断。
4. AI 协作区可收起地停靠在底部，并可展开为右侧浮层。它继续使用现有会话、Run、
   SteeringInput 和证据协议，但所有“改写论文”的结果均先成为可审阅 revision，不能
   静默覆盖 LaTeX source。
5. 证据引用、诊断和 revision 必须连接 source span；从 AI 建议、PDF 文本或 LaTeX
   位置都能打开同一个证据 inspector。
6. 桌面端的左下角账户区成为本地/云端连接与身份的入口。远程模式只能在具备真实
   认证、配置持久化和 API compatibility check 后启用，不能复用 `local-user` header
   冒充云端身份。

## Non-goals

- 不在本变更中实现任意代码执行、Shell 或不受限 LaTeX package 下载。
- 不把普通聊天记录当成论文版本，也不从模型文本猜测文件变更。
- 不在未完成远程认证前发布可点击但无实际后端目标的“云端模式”。
- 不替换既有 RAG、证据存储或 durable task runtime；作者工作区消费其明确的 API。

## Impact

- Backend: paper draft/revision/compile domain contracts、SQLite adapters、受限 compile worker、
  FastAPI routes 和 artifact storage。
- Web: 新的论文 workspace route、Monaco/CodeMirror 适配、PDF viewer、可停靠 AI panel、
  source/evidence navigation 和 connection menu。
- Desktop: preload/main 中最小的连接配置与安全存储边界；本地 backend 或已认证远端 API
  的选择不进入 React 页面业务逻辑。
- Docs/tests: desktop 架构、论文工作流、编译安全 runbook、repository/API/UI/e2e tests。
