# 技术债登记表

规则（AGENTS.md §8.4）：新增债务必须先登记；偿还时更新状态并在
[PLANS.md](../PLANS.md) 立项。每项标注登记日期；影响写清楚"谁现在付出什么代价"，
不写泛泛的"不优雅"。登记日期统一为首次盘点日：2026-08-23。

| # | 登记项 | 影响 | 状态 | 偿还路径 |
|---|---|---|---|---|
| a | 记忆双表分裂：固化写 legacy `memory_items`（`agent/memory/repository.py`），检索读 governed `context_memory_items`（`agent/adapters/orm/memory_repository.py`） | 迁移后新固化的记忆对检索不可见，长期记忆功能事实上退化 | 已登记 2026-08-23 | 统一读写到 governed 表：consolidation 改写 ORM memory_repository，legacy 表只读迁移后删除 |
| b | legacy 进程内检索器 `agent/rag/hybrid.py` 与 LanceDB 生产链并存：`create_project_evidence_retriever`（评测/直连路径）仍走 hybrid/brute-force，生产是 `DynamicProjectEvidenceService` | 两条检索语义不一致；live 评测的真实论文 e2e 走 brute-force 路径，与生产检索行为有偏差 | 已登记 2026-08-23 | live harness 切到 DynamicProjectEvidenceService（预置语料先过 LanceDB 摄取），hybrid.py 收敛为离线工具或删除 |
| c | `agent/metrics.py` 遗留 performative 计数器：`extract_replan_rounds` 等待 `performative=="replan"` 事件，当前 trace 中间件不再发射 | 指标恒为 0，制造"有监控"假象 | 已登记 2026-08-23 | 删除 replan 计数或让 plan 中间件发射真实事件；以 trace 事实重建指标口径 |
| d | `rag_rerank_candidate_k` 配置定义但从未消费（`agent/settings.py` 定义，全仓无读取方） | 用户改配置无效果，配置面撒谎 | 已登记 2026-08-23 | 接入 LanceDB 重排候选数或从 settings 删除该键 |
| e | 文档提及 RapidOCR，实际引擎已是 PaddleOCR（`agent/adapters/paddle_ocr.py`；`docs/architecture/agent-runtime.md`、`README_EN.md` 仍写 RapidOCR） | 误导贡献者与打包排障（依赖体积、模型目录均不同） | 已登记 2026-08-23 | 修正两处文档为 PaddleOCR；打包文档核对模型资产清单 |
| f | openspec 存量 spec 为 delta 格式对 CLI 不可见：11/13 spec 缺归档器要求的 Purpose 与全量 scenario | `openspec validate` 无法覆盖存量 spec，漂移无法机器发现 | 已登记 2026-08-23 | 归档器逐个补 Purpose、MODIFIED 需含全部 scenario；归档时转全量格式 |
| g | 检索质量无量化指标：无 recall@k / RAGAS / 金标问题集 | 检索改动只能靠 live 端到端数字间接观察，回归无法定位到检索层 | 已登记 2026-08-23 | 用评测语料建金标集（19 用例已含 chunk 级证据引用，可作起点），先做 recall@k |
| h | 委派触发方差未量化：pass^k 重复试验未落地 | 无法区分"能力不足"与"不稳定"；委派预算（generic-agent-harness）缺乏依据 | 已登记 2026-08-23 | tasks 3.10/7.6：trials 1–5 已进 API，落地 pass^k 报表后量化 |
| i | `repository_guard` 超限文件基线只减不增（`scripts/code_size_baseline.json`） | 基线是上限天花板；若无清理节奏，超限文件永久合法存在 | 已登记 2026-08-23 | 每次触碰基线内文件时顺手减行；定期（发版节点）清理 stale 条目 |
| j | 域提示提及 `list_document` 但部分执行路径未注册该工具（提示在 `agent/prompts/paper_domain.py:15,55`；工具仅在 `deps.list_documents_fn` 可调用时注册，`agent/capabilities/document.py`） | 模型按提示调用会得到"未知工具"报错，浪费轮次并污染 trace | 已修复 2026-08-23（最后缺口 live harness 在 `evals/live_harness.py` 补齐 `list_documents_fn`） | 常态规则见 [../design-docs/core-beliefs.md](../design-docs/core-beliefs.md) §5：新增执行路径必须提供完整工具清单 |
