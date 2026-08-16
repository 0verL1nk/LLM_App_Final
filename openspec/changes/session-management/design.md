# Design: Session Management

## 1. Design decisions

### 1.1 删除范围:仅探索分支,主会话不可删

主脉络是项目的对话主干与分支的父节点(`parent_session_uid`),删除它会
产生孤儿分支并破坏"研究脉络"的产品结构。v1 规则:

- 主会话(无 parent)的 DELETE 返回 `409 main_session_protected`;
- 分支删除为软删除:`deleted_at` 标记,所有列表/消息查询过滤;
- 分支的子级不存在(结构两级),无级联子会话问题。

消息与 run 行物理保留:run/事件日志是审计事实(与 durable runtime 的
"历史可读"语义一致),删除只影响会话视图。若未来需要彻底清理,提供
单独的项目级数据清理,不在会话操作里夹带。

### 1.2 重命名不改身份

会话标识始终是 `session_uid`;标题是展示元数据。重命名校验:非空、
trim、长度上限(120)。自动生成的会话标题(session_titles 异步生成)
与手动改名的关系:一旦用户手动改名,标记 `title_source = user`,后续
异步标题生成不再覆盖(生成器跳过 user 标题)。

### 1.3 删除后的导航

删除当前正打开的分支会话时,前端跳回主脉络;删除其他分支时保持当前
视图。列表即时更新,不整页刷新。

## 2. API

```text
PATCH  /projects/{p}/sessions/{s}   { title }        → 更新后的会话
DELETE /projects/{p}/sessions/{s}                    → 202 幂等;
                                                    主会话 409 main_session_protected
```

## 3. Testing

- 重命名:列表/标签标题联动、user 标题不被自动生成覆盖、空名拒绝。
- 删除:分支从列表与消息查询消失、幂等、主会话被拒、当前分支删除后的
  导航、归属校验(他人项目 404)。
- 既有两级结构与会话消息读写回归。
