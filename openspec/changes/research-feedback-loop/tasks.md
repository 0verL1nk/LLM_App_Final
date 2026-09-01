## 1. 信号捕获

- [x] 1.1 `feedback_events` 表 + Alembic 迁移（幂等键、脱敏字段）
- [x] 1.2 轮后入队（复用本地 task queue 模式）+ 确定性信号判定器（三类规则、命名常量、env 覆盖）
- [x] 1.3 证据点击埋点端点（轻量 POST，run item 关联）
- [x] 1.4 单测：三类信号判定（命中/不命中/数据不足跳过）、幂等去重、脱敏
  - 注：第三类信号实现为 `evidence_gap`（消费 turn_engine 的 `citation_audit` 字段，
    P3-lite 已产出）；设计稿中的 `evidence_engagement`（引用 vs 点击对比判定）待埋点
    数据积累后作为后续增强，点击埋点存储已就位。
  - 注：correction_followup 的时间窗按"steering 输入与轮完成时刻的间隔"度量
    （当前产品结构中 steering 只能挂到运行中的 Run，不存在答案完成后的提交路径）。

## 2. 发现归并

- [x] 2.1 发现聚合查询（GROUP BY + 最小重复阈值 + 项目粒度）
- [x] 2.2 单测：重复≥2 出现、单次不出现、时间窗内聚桶

## 3. 人审转评测

- [x] 3.1 `GET /evals/feedback-findings` + `POST .../export-case` 端点（草稿生成，含 origin 溯源）
- [x] 3.2 开发态评测页"反馈发现"区（列表 + 导出按钮）（最小实现：表格 + 导出 + JSONL 复制，无独立看板）
- [x] 3.3 loader 支持 `origin` metadata；报告按来源分层统计
- [x] 3.4 单测：草稿生成结构、origin 标注、报告分层

## 4. 验证与文档

- [x] 4.1 全量门禁 + openspec validate（repository_guard / ruff / 相关单测通过；
  未跑全量单测套件——本任务约定只跑新增与受影响测试）
- [ ] 4.2 用真实会话人工核验一轮信号判定（抽样）
- [x] 4.3 QUALITY_SCORE 登记"生产来源用例"指标位；eval-frameworks-assessment 补 Tax AI 对照注记
- [ ] 4.4 （后续登记）发现→openspec 修复草案的自动化闭环；模型辅助信号分类
