# 内置评测进度前端（进行中）

目标：把任务完成度评测搬进应用——用户在 web 界面发起 live 评测、轮询观察进度、
查看 trials/pass^k 与逐用例诊断，而不是依赖 Makefile + JSON 报告。

## 分层现状

- **已完成（后端服务）**：`agent/application/evals/run_service.py`——评测循环跑在后台
  线程（绝不进入 API 请求路径），内存注册表持有每次运行的逐用例状态
  （pending/running/passed/failed/errored + 摘要），报告产物落 `data/evals/`。
  复用 `agent/application/evals/live_harness.py`（CLI 冒烟 runner 与应用内服务驱动
  同一条 canonical turn 路径：`execute_turn_core` + 真实检索器）。
- **已完成（API）**：`api/eval_routes.py`，前缀 `/evals/task-completion`：
  `POST /start`（`trials` 1–5）、`GET /runs`、`GET /runs/{uid}`——轮询快照式读取，
  与进度注册表一一对应。
- **待建（web）**：`web/src/pages` 目前没有评测页面（现有四页：library、
  project-overview、research、settings）。

## 剩余工作

1. `web/src/lib` 新增 eval query（TanStack Query 轮询 `GET /runs/{uid}`，zod 契约），
   复用 [api() helper](../../FRONTEND.md) 与 SSE 无关的轮询模式。
2. 新页面组合：发起表单（fixture 选择、trials 数、web 回退开关）+ 运行列表 +
   单次运行详情（逐用例状态、结果层/过程层/证据覆盖、trials 分栏展示）。
3. trials/pass^k 展示：`run_service` 的快照已透出 `trials` 摘要；前端需把
   多次试验聚合为 pass^k 读数（同一用例 k 次中至少一次通过的比率），为
   [live-agent-task-eval-baseline](live-agent-task-eval-baseline.md) 的 7.6 方差量化
   提供数据入口。
4. 断线与并发：同一时刻只允许一个运行（后端已拒绝并发 start）；页面需如实展示
   该约束，不发明排队假象。

## 边界

- 前端只读服务端事实（AGENTS.md §3.16）：进度、状态、失败原因全部来自快照 API，
  禁止 mock 或本地推算百分比。
- 报告解读规则（scenario=校准、live=度量）沿用
  [openspec/changes/live-agent-task-eval-baseline/design.md](../../../openspec/changes/live-agent-task-eval-baseline/design.md)。
