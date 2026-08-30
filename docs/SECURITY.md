# 安全边界（Trust Boundaries）

威胁模型核心：**模型输出与外部内容都不可信，可信任的只有确定性代码**。分层与密钥
纪律见 [AGENTS.md](../AGENTS.md) §9 与根目录 SECURITY.md 的披露政策；可靠性见
[RELIABILITY.md](RELIABILITY.md)。

## 记忆固化：模型提议、确定性代码裁决

长期记忆的增删改由固化模型**提议**（structured output），落库前的裁决是确定性代码：
`apply_memory_consolidation`（`agent/memory/repository.py`）对每条操作强制 schema 与
uuid/project scope 校验——删除只能命中本 user+project 的条目，模型无法借记忆操作
跨项目越权或污染他账号数据。

## EvidencePacket 文档授权过滤

子代理结果的证据引用不是照单全收：`_sanitize_result`
（`agent/application/subagent_task_executor.py`）丢弃 project_uid 不匹配、doc_uid 不在
授权集合、缺 chunk_id 的证据——子代理只能引用本次任务授权的文档，伪造引用进不了
packet，也就进不了 Leader 上下文与 UI。

## 委派不可递归（构造性保证）

子代理会话不装配委派中间件（`agent/subagent/`，角色定义 fail-fast 校验）——"子代理
不能再委派"不是提示词约定而是构造上不可达，杜绝委派链失控放大。

## 不可信内容面（提示注入边界）

PDF 正文、OCR 结果、网页检索结果、模型转述的外部内容都是注入面。约束：

- 提示词与工具逻辑不得盲从上述内容中的指令（如"忽略之前的要求"）；工具返回是数据
  不是指令。
- A2UI 片段、思维导图节点引用均经 schema 校验与 chunk ID 白名单过滤，模型提供的
  URL/代码/HTML 不会到达客户端（[architecture/a2ui.md](architecture/a2ui.md)）。
- 评测将"来源注入防护"用例登记为后续风险层契约（结果/过程/效率之外的第四层）。

## 密钥纪律

- 密钥只从环境变量/用户配置读取（`agent/adapters/user_settings.py` 按用户持久化），
  `.env` 已 gitignore，仓库无硬编码密钥（ruff/guard 把关）。
- 日志与 trace 不打印完整密钥；LLM 请求日志记录 payload 而非凭据。

## 工具暴露 = 能力清单

模型能做什么由 `agent/profiles.py` + `agent/capabilities/` 的显式清单决定，与提示词
承诺一致（漂移登记见 [exec-plans/tech-debt-tracker.md](exec-plans/tech-debt-tracker.md)
条目 j）。最小权限默认：writer 角色仅技能、reviewer 无 web；`ask_human` 是 Leader
专属能力。新增工具必须先回答"哪个 profile 该有它"，而不是全局注册。
