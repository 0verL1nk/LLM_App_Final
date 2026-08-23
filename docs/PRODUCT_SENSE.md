# 产品原则

产品为谁、凭什么立足。痛点依据见 [product-specs/paper-reading-pain-points.md](product-specs/paper-reading-pain-points.md)；
主流程规格见 [product-specs/research-workflow.md](product-specs/research-workflow.md)。

## 1. 服务科研人员的阅读流

产品主线是"读论文、做综述、写东西"的工作流本身，不是通用聊天机器人。功能排序以
痛点分析为准：证据定位、跨论文综合、图表提取、可复现性判断优先于花哨的对话体验。
写作工作区（paper-authoring-workspace）同样围绕"正在写的论文是主对象"展开。

## 2. 证据优先：可核查大于流畅

一条能点开看到 PDF 第几页哪个区域的引用，价值高于一段更流畅但没有出处的总结。
因此证据契约贯穿工具、提示词、子代理与 UI（行内 `[n]` + 页面高亮）；跨任务合并保留
冲突双方主张等 Leader 裁决，而不是静默择一。回答的可解释性（研究检查器：上下文构成、
已用记忆、委派任务）是功能而不是调试面板。

## 3. 宁弃答不编造

语料未覆盖时显式说明并给出下一步（补检索、换问题），不把综合推断伪装成论文结论；
评测用弃答用例（`project_abstain_001`）和虚假前提纠错用例把这条底线钉进契约。
没有证据的内容必须标注为推断或待验证。

## 4. 本地优先

检索栈（PaddleOCR、FastEmbed 嵌入、FlashRank 重排、LanceDB 向量+全文）全部本地
离线运行：隐私（论文草稿不出本地）与成本（无按量检索费用）都是产品属性，不是实现
细节。生成模型走用户自配的 OpenAI 兼容端点，工具不绑定厂商；桌面打包保持这套栈
可离线开箱（GPU OCR 包可选）。

## 5. 模式可手选，auto 只是兜底

react / plan_execute / agent_teams 是用户可见、可理解的选择——用户知道自己在用
"直接检索"还是"团队协作"；auto 路由只在用户不表达偏好时兜底，且路由理由
（route_reason）随 Run 持久化，可解释、可回放。不为"智能感"隐藏控制权。

## 6. 迭代以评测驱动

产品能力的变化用任务完成度基线度量（scenario 校准 + live 度量双层，见
[agent-evals.md](agent-evals.md)）：改提示词、改检索、改委派都要对基线数字负责；
Bad Case 是需求来源，不是噪音。
