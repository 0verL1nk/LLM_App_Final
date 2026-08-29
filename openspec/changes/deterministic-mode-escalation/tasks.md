## 1. 路由重写

- [x] 1.1 `resolve_execution_route` 改为结构规则（document_count 阈值常量命名；删除关键词表与长度阈值；保留 prompt 审计参数）
- [x] 1.2 `research_workspace.prepare_turn_run` 传入就绪文档计数（`list_ready_project_documents`）
- [x] 1.3 更新 `tests/unit/test_execution_routing.py`：结构规则全覆盖 + 断言关键词不再触发升格（防伪智能回归）
- [x] 1.4 调用方回归：route_reason 透传到 Run 记录与 API 响应不变

## 2. 验证与文档

- [x] 2.1 门禁：目标单测 + ruff + repository_guard + openspec validate
- [x] 2.2 验证轮与数字回填（两轮）：
  - v1 工具结果内提示：**被评测抓出污染 bug**——追加文本破坏 search_document JSON 证据载荷（覆盖 100%→79%）、委派行为紊乱（hybrid 3→0）；修复为 wrap_model_call 系统消息注入（提交 d4a9e31 前置）
  - v2 修复后：证据恢复 89%、 18/19（基线含 2 个 False，达成设计目标）；单轮 5/19 对 10/19 落在已知噪声带内不能定论，但暴露交互：建计划后不回写步骤状态（ratio 失败）→ nudge 文案已补「完成每步后回写状态」
  - 结论：结构路由+nudge 保留（计划在场率是设计目标且已验证）；完整 A/B 需双臂 pass^k（登记 live-agent-task-eval-baseline §8.5 承接）
