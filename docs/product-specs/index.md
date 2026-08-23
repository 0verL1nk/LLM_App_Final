# 产品规格索引

本目录是产品层规格：用户可感知的工作流、痛点与配置面。系统如何实现见
[ARCHITECTURE.md](../../ARCHITECTURE.md) 与 [../architecture/](../architecture/)；
产品原则见 [../PRODUCT_SENSE.md](../PRODUCT_SENSE.md)。

| 规格 | 位置 | 说明 |
|---|---|---|
| 研究工作流（核心） | [research-workflow.md](research-workflow.md) | 项目 → 文档库 → 研究会话 → 证据引用回答 → 两层记忆 → 研究检查器的端到端主流程。 |
| 论文阅读痛点与能力差距 | [paper-reading-pain-points.md](paper-reading-pain-points.md) | 2026-03 对科研人员阅读痛点的归纳与产品能力映射，是功能优先级的原始依据。 |

## 模型与生成配置（model-settings）

用户自配 OpenAI 兼容生成端点，不绑定任何厂商：

- **配置面**：设置页（`/settings`）配置 API key、模型名、base URL，按用户持久化
  （`agent/adapters/user_settings.py`）；所有角色（leader 与子代理、记忆固化、评测裁判）
  复用同一用户模型构造（`agent/llm_provider.py`）。
- **thinking 开关按 provider 映射**（`agent/llm_provider.py::_thinking_extra_body`）：
  DashScope 混合模型发 `enable_thinking`（显式 `False` 才能关闭 Qwen 系默认思考）；
  MiniMax M3 发 `thinking.type`（`adaptive`/`disabled`，`enabled` 会被 400 拒绝，M2.x
  无法关闭故不发）；OpenAI 官方端点映射 `reasoning_effort`。provider 判断基于归一化
  host，不信任 URL 子串。
- **边界**：thinking 是用户开关而非模型自治；provider 不支持时不发标志，绝不猜测。
- 演进方向（按角色绑定不同模型）登记在
  [../exec-plans/active/generic-agent-harness.md](../exec-plans/active/generic-agent-harness.md)。
