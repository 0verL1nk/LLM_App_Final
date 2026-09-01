## 1. P2 实现

- [x] 1.1 分层模块:形状函数(截断保引用字段/短文不截/提示注入)+ read_evidence 工具
- [x] 1.2 能力接线:闭包会话缓存,默认关,env 覆盖
- [x] 1.3 单测 ×5:截断语义/默认不变/命中与未命中/会话隔离

## 2. P3-lite 实现

- [x] 2.1 turn_engine 收尾 citation_audit 判定 + 告警
- [x] 2.2 turn engine 回归测试通过(15/15)

## 3. 验证

- [ ] 3.1 全量门禁 + openspec validate
- [ ] 3.2 A/B 双臂 pass²(v2 快照,M3):treatment = AGENT_EVIDENCE_TIERED=1;
      预登记判定:treatment final 层不低于 control、工具调用增幅 ≤30%
- [ ] 3.3 QUALITY_SCORE 登记 A/B 结果;若净负保持默认关并把结论回填
