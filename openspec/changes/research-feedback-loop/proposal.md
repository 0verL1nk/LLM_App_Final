## Why

评测体系的语料目前是 19 条自写用例（"自写自测"循环，已在 QUALITY_SCORE 诚实登记）。
OpenAI Tax AI（2026-07《building-self-improving-tax-agents-with-codex》）验证的路径是：
**把生产使用本身变成结构化失败信号 → 归并成发现 → 经人审后转为评测目标 → 修复 → 回归**。
PaperSage 已具备该闭环的后三段（评测基础设施、追踪、openspec 流程、回归基线），
唯独缺第一段：用户在研究会话中的修正行为没有变成结构化数据。

用户的修正信号已经存在于产品交互中，只是未被捕获为证据：

1. **追问式修正**：答案给出后用户的 steering 追问（重问、改写、纠偏）——
   `SteeringInputMiddleware` 已持久化这些输入，但没有判定"这是修正还是新话题"。
2. **模式切换重问**：同一问题换 execution_mode 重发（对路由不满意的信号）。
3. **证据交互**：答案引用了 N 条证据，用户实际点开/采纳了哪些（引用有效性的间接信号）。

## What Changes

- **信号捕获**：轮后异步任务（复用 memory_events 的 durable 事件+worker 模式）把
  上述三类交互写入 `feedback_events` 表；v1 用确定性规则判定信号类型（相似度阈值
  判"追问式修正"、模式切换比对、证据点击比对），不引入模型分类。
- **归并发现**：SQL 聚合视图按项目/文档/信号类型统计重复模式，`feedback_findings`
  输出"重复 N 次的同类修正"式发现（对应 Tax AI 的审查行归并）。
- **人审转评测**：REST 端点 + 开发态评测页新增"反馈发现"区：列出发现（次数、样例、
  涉及文档），一键导出为**评测用例草稿**（JSONL 行，prompt 取用户原始问题，rubric
  骨架由发现类型生成）——操作者审核后手工并入 fixture，不做全自动入库（伪智能禁令）。
- **不做**（登记为后续）：自动生成 openspec 修复草案的无人值守闭环；模型分类信号。

## Capabilities

### New Capabilities

- `research-feedback-loop`：信号捕获、发现归并、人审转评测草稿的完整语义。

### Modified Capabilities

- `agent-evals`：评测 fixture 新增"生产来源"用例的 provenance 标注（case metadata
  `origin: production-finding`），基线报告可区分自写与生产用例的通过率。

## Impact

- 受影响代码：`agent/application/research_workspace.py`（轮后入队）、新
  `agent/memory/`同级的反馈事件模块、`agent/adapters/orm/`（表+迁移）、`api/`（端点）、
  web 评测页（开发态新增发现区）。
- 隐私：反馈事件只存项目内已有会话数据（prompt/答案片段/信号类型），不新增外部传输。
- 依赖：复用 durable 事件模式（幂等键、租约认领、载荷脱敏），不引入新基础设施。
