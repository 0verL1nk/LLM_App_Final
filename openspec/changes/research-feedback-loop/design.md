# Design: research-feedback-loop

## D1：三类信号与确定性判定（v1 不用模型分类）

| 信号 | 判定规则 | 数据来源 |
|---|---|---|
| `correction_followup` | 答案完成后 N 分钟内的 steering 输入，与上一 prompt 归一化相似度 ≥ 阈值（局部敏感的字符三元组 Jaccard，阈值命名常量）或以"不对/不是/重新/更正"类开头词触发 | steering 输入 + 上一轮 prompt/答案（均已在消息与 run item 中） |
| `mode_switch_reask` | 同会话内相邻两轮 prompt 相似度 ≥ 阈值 且 execution_mode 不同 | Run 的 requested/resolved mode + prompt |
| `evidence_engagement` | 轮答案引用的证据数 vs 用户实际展开/点击的证据集合 | 前端证据点击埋点（新增一条轻量 POST，写入 run item 附表） |

规则常量命名并可 env 覆盖；判定失败（数据不足）跳过而非猜测。

## D2：存储与归并（复用 memory_events 的 durable 模式）

- 表 `feedback_events(id, user_uuid, project_uid, session_uid, run_uid, signal_type,
  prompt_digest, payload_json, created_at)`，幂等键 = sha256(user+run+signal_type+digest)。
- 轮后入队走本地 task queue（与记忆固化同队列），完成即脱敏 prompt 全文（只留摘要与
  digest），降低表内敏感面。
- 发现聚合：`feedback_findings` 为查询期物化（SQL GROUP BY signal_type + doc_uid 桶 +
  时间窗），不落第二张表——重复 ≥ FINDING_MIN_REPEATS（默认 2）才出现在发现列表。

## D3：人审转评测草稿

- `GET /api/v1/evals/feedback-findings`：发现列表（类型、次数、最近样例、涉及文档）。
- `POST /api/v1/evals/feedback-findings/{id}/export-case`：返回 JSONL 行草稿——
  prompt 取该发现最近一次的原始问题；rubric 骨架按信号类型给检查项（如
  correction_followup → "答案必须针对用户修正点重答且引用证据"）；metadata 带
  `origin: production-finding` 与 finding id。草稿写入文件由操作者执行（响应给出
  建议路径），不自动改动 fixture 文件。
- 前端：开发态评测页新增"反馈发现"卡片区（复用进度页的 DEV-only 门控）。

## 风险

- 相似度误判把新话题当修正：阈值从紧（宁漏勿滥），误判只影响发现列表不直接影响评测。
- 埋点缺失（旧前端）：evidence_engagement 信号在埋点上线前自然为空，不阻塞其余信号。
- 单人产品信号量小：FINDING_MIN_REPEATS=2 起步，聚合粒度按项目而非全局。
