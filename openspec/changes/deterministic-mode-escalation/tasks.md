## 1. 路由重写

- [x] 1.1 `resolve_execution_route` 改为结构规则（document_count 阈值常量命名；删除关键词表与长度阈值；保留 prompt 审计参数）
- [x] 1.2 `research_workspace.prepare_turn_run` 传入就绪文档计数（`list_ready_project_documents`）
- [x] 1.3 更新 `tests/unit/test_execution_routing.py`：结构规则全覆盖 + 断言关键词不再触发升格（防伪智能回归）
- [x] 1.4 调用方回归：route_reason 透传到 Run 记录与 API 响应不变

## 2. 验证与文档

- [x] 2.1 门禁：目标单测 + ruff + repository_guard + openspec validate
- [ ] 2.2 全量 19 用例快照跑一轮（v2 证据），对比 10/19 基线观察 plan_passed 变化，数字回填本变更
