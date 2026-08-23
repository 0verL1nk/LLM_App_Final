# LangChain/LangGraph 踩坑实录

本仓库与 LangChain/LangGraph 栈协作中踩过的真实坑。每条都有代码锚点；新代码 Review
时对照检查。背景架构见 [../architecture/agent-runtime.md](../architecture/agent-runtime.md)。

## 1. `from __future__ import annotations` 会杀死 ToolRuntime 注入

注解被字符串化后，`langchain_core` 无法通过 `inspect` 识别 `runtime: ToolRuntime`
是注入参数而不是模型可见参数——运行时值永远到不了函数体，工具真实调用必崩。
最阴险的是：**罐头测试测不出来**（scenario 回放不经过真实注入路径），只有真实模型
调用才暴露；该 bug 同时击穿了生产 agent_teams 委派与 live 评测
（openspec change `live-agent-task-eval-baseline` tasks 7.2）。

修复：`agent/tools/plan_tools.py`、`agent/middlewares/durable_delegation.py` 移除该
import 并留注释防回退；补真实 agent 路径回归测试
`tests/unit/test_agent_tool_runtime_injection.py`。规则：需要注入参数的工具模块
**禁止** `from __future__ import annotations`。

## 2. 自定义工具用 `StructuredTool.from_function` 官方模式

见 `agent/tools/plan_tools.py`：`func` + 显式 `args_schema`（pydantic）+
`infer_schema=False`。显式 schema 保证参数契约稳定、校验先行；`infer_schema=False`
避免从函数签名二次推导引入歧义。修订冲突用领域校验器表达
（`UpdatePlanInput.validate_dependencies`），错误在工具边界变成可读 ToolMessage。

## 3. `invoke_structured_model` 必须对损坏 JSON 重试

长推理（尤其裁判逐条核查协议）会让模型在 JSON 前后混入推理文本或截断。
`invoke_structured_model` 对损坏 JSON 重试一次再抛错；评测 harness 在 turn 执行与
裁判调用两层各容错一次（重试→记错误→继续），单用例失败不拖垮整轮基线
（`agent/application/evals/harness.py`、openspec change tasks 7.3）。

## 4. SummarizationMiddleware 独占活动图压缩

LangChain `SummarizationMiddleware` 是活动图消息压缩的唯一所有者
（`agent/middlewares/builder.py`）。其他层（中间件、工具、应用层）不得再截断或改写
历史消息——双重压缩会互相踩踏导致上下文不可推理。项目长期记忆是独立的检索注入层，
不参与活动图压缩。

## 5. 中间件只允许一个 provider-facing SystemMessage

每次模型请求至多一条系统消息，存于 `ModelRequest.system_message`。动态指令必须用
`request.override(system_message=...)` 合并进这条消息；**禁止**向历史插入新的
SystemMessage（`agent/middlewares/system_message.py`、`turn_context.py`）。插入历史会
造成 provider 上下文里系统指令漂移、缓存失效与不可预期行为。
