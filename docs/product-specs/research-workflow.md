# 研究工作流（核心产品规格）

PaperSage 的主流程。产品是项目优先：一个项目拥有自己的文档库、会话、检索范围、
记忆与 Agent 活动。痛点来源见 [paper-reading-pain-points.md](paper-reading-pain-points.md)。

## 1. 项目与文档库

- 用户创建项目（`/projects`），向项目上传 PDF/DOCX/PPTX/图片等文档
  （`/projects/$projectId/library`）。
- 上传即入队摄取：抽取 →（扫描件）OCR → 切块 → 嵌入 → 发布 LanceDB → 标记 ready。
  摄取进度按真实阶段展示（completed/total 页数与块数），无度量工作的阶段不显示百分比。
- 只有 ready 的 `(doc_uid, index_version)` 进入检索；部分摄取或旧版本不会泄漏进结果。
- 上传与索引永不阻塞会话创建。

## 2. 研究会话与模式选择

- 每个项目可开多个研究会话（`/projects/$projectId/research/$sessionId`），
  会话切换在侧栏，证据与活动在检查器内展开而非跳页。
- 模式可手选（`mode-selector`）：`react`（直接检索作答）、`plan_execute`（先建计划再
  执行）、`agent_teams`（Leader 并行委派 researcher/reviewer/writer）；`auto` 是兜底路由，
  不是主推。Run 同时持久化 requested_mode 与 resolved_mode + route_reason，续跑沿用解析结果。

## 3. 证据引用回答

- 域提示要求：回答中的每个文档事实与关键结论紧邻
  `<evidence>chunk_id|p页码|o起止偏移</evidence>` 引用（`agent/prompts/paper_domain.py`）。
- 前端把证据渲染为行内 `[n]` 引用（`evidence-inline-citations.tsx`），点击打开证据
  检查器：按页预览原文并高亮定位（`evidence-preview.tsx`，页码 + bbox polygon）。
- 子代理产物先经授权过滤（仅项目内、授权文档、真实检索过的 chunk 才能进
  EvidencePacket），跨任务合并保留双方主张与来源，冲突留给 Leader 裁决。
- 语料未覆盖时宁弃答不编造（评测含弃答与虚假前提用例作为契约）。

## 4. 两层记忆

- **会话层压缩**：长会话由 `SummarizationMiddleware` 独占压缩活动图消息；
  会话摘要持久化在 `session_context_summaries`，恢复会话不丢上下文骨架。
- **项目长期记忆**：每轮结束落一条 durable memory event，后台固化（模型提议增删改、
  确定性代码做 schema 与项目/user scope 裁决），检索用语义嵌入而非关键词；
  项目内跨会话复用，过期项显式清理。

## 5. 研究检查器（inspector）

研究会话右侧检查器（`research-inspector.tsx`）暴露三个事实面：

1. **上下文构成**：本轮上下文里有什么——资料与记忆范围、已使用的长期记忆
   （`context-composition.tsx`），模型看到的事实可审计。
2. **已用证据**：引用证据列表与跨任务证据合并（claims、开放问题、未决冲突，
   读自持久化的 `evidence_merge` 产物）。
3. **委派任务**：每个委派子任务的角色、并行状态、结果与失败状态——全部来自
   真实 tool-call/result 与任务表，不由 UI 推测。

检查器读的是服务端事实（Run/RunItem/Task），这是产品承诺：状态可解释、
证据可核查、过程可回放（断线经事件序号重放恢复）。
