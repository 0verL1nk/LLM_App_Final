## Why

评测矩阵的模型×证据交叉实验暴露两个 harness 缺口:(1) M2.5 在富证据(v2)下
不升反降(7→4/19)——单条工具结果的全文洪泛压垮指令遵从弱的模型;(2) 答案
引用缺失只有评测侧度量(evidence 覆盖率),生产运行对此不可见,无法进入反馈闭环。

## What Changes

- **P2 证据分层注入**(`AGENT_EVIDENCE_TIERED=1` 开启,默认关):search_document
  证据 text 截为预览(命名常量+env),引用字段完整;新增 `read_evidence(chunk_id)`
  按需取回全文,闭包缓存每会话隔离;载荷携带扩展提示。
- **P3-lite 引用审计**:turn_engine 收尾确定性判定 `citation_audit`(检索到证据
  但答案零引用 → failed),入结果+告警,喂 evidence_gap 反馈信号。完整核验轮
  (regeneration)登记为 durable-runtime reviewer 的后续项。

## Capabilities

### New Capabilities

- `evidence-tiering`:预览优先的证据注入 + 按需全文取回 + 会话隔离缓存。

### Modified Capabilities

- `agent-evals`:A/B 双臂验证(treatment = 分层开),判定规则预登记。
- `research-feedback-loop`:evidence_gap 信号消费 `citation_audit=failed`。

## Impact

- 代码:agent/capabilities/evidence_tiering.py(新)、agent/capabilities/document.py
  (接线)、agent/application/turn_engine.py(审计三行)、tests。
- 风险:分层开时 UI 证据面板显示预览文本(可接受,flag 默认关);read_evidence
  增加一次工具往返(效率层 A/B 考量项)。
