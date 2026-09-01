# Design: p2-evidence-tiering

## P2 证据分层注入(AGENTS 默认关:AGENT_EVIDENCE_TIERED=1 开启)

矩阵数据(M2.5 富证据 7→4/19)表明:单条 search_document 工具结果携带 8 段全文
(~4KB)会压垮指令遵从较弱的模型。分层注入把证据 text 截为预览
(AGENT_EVIDENCE_PREVIEW_CHARS,默认 160),引用字段(chunk_id/doc_uid/page_no/
offset)原样保留;新增 `read_evidence(chunk_id)` 工具按需取回全文。

- 缓存 = `build_document_tools` 闭包字典 → 每会话一份(生产/live harness 均然),
  会话结束随工具一起销毁,无跨会话泄漏、无全局增长。
- 预览载荷带 `tiering_hint`,模型从工具结果本身学会扩展路径(工具结果近场提示
  遵从率高于系统提示——nudge 系列实验结论)。
- 默认关:与 nudge 同样的教训,先由 A/B 证明净收益再转默认。
- 评测影响:turn_engine 的证据提取读载荷 JSON 字典,text 长度不影响 evidence_items
  收集;引用语法未被触碰。

## P3-lite 引用审计(确定性标注,不重生成)

完整"核验轮"(答案后再生)与流式架构冲突:answer deltas 在核验点之前已发给
用户,二次生成会重复输出。正确归宿是 durable runtime 的 reviewer 子代理
(已登记)。本轮落可行半步:turn_engine 收尾处确定性判定
`citation_audit = passed|failed|not_applicable`(检索到证据但答案零引用 → failed),
写入 turn 结果并告警——喂 research-feedback-loop 的 evidence_gap 信号,
让"引用缺失"从评测指标升级为生产可观测事实。

## 验证

- 单测:截断保引用字段/短文不截不加提示/默认关零变化/缓存会话隔离/read_evidence
  命中与未命中。
- A/B:双臂 pass²(v2 快照,M3),处理臂 AGENT_EVIDENCE_TIERED=1;判定规则预登记
  (处理臂 final 层不降、效率层工具调用增幅可接受)。
