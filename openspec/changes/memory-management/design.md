# Design: Memory Management

## 1. Design decisions

### 1.1 复用既有数据平面,不建第二份存储

长期记忆已有仓储与 consolidator 的结构化增删改(ADD/UPDATE/DELETE/
NOOP 四操作)。用户 CRUD 走同一张表、同一套字段:新增/编辑写入时标记
`source = user_managed`;系统整理继续走 consolidator。管理面板读的与
检索注入读的是同一份事实。

### 1.2 用户编辑与系统整理的冲突:用户赢一次,系统可再改

不引入完整版本控制(YAGNI)。规则:

- 用户编辑/删除后,记录 `last_updated_by = user` 与时间戳;
- consolidator 在下一轮整理时**可以**继续演化该条目(系统基于新对话
  理应能更新过时信息),但面板中该条目保留"曾被手动修改"标记,
  用户可见系统何时改动了它;
- 用户删除:立即从注入范围移除;consolidator 不得凭旧上下文复活已删除
  条目(整理输入不含已删除项,天然满足,需测试钉死)。

### 1.3 列表与检索解耦

管理面板查询全部条目(分页 + 类型筛选 + 关键词搜索);检索注入逻辑
不变(语义检索 top-k)。面板按 `memory_type` 展示分组计数
(semantic / episodic / procedural / user_managed 若有独立类型)。

### 1.4 来源诚实原则

provenance 字段按仓储现状:有来源记录(如整理自哪轮 run)就显示链接,
没有就显示"系统整理"。不为凑 UI 编造来源。这是 durable-research §1.1D
(ResearchArtifact provenance)方向的第一块砖,但本变更不实现其合同。

## 2. API

```text
GET    /projects/{project_uid}/memories?type=&q=&page=   → 分页列表
POST   /projects/{project_uid}/memories                  {type, content}
PATCH  /projects/{project_uid}/memories/{memory_uid}     {content}  (带 last_updated 乐观锁)
DELETE /projects/{project_uid}/memories/{memory_uid}     (幂等)
```

归属校验与现有项目路由一致;PATCH 冲突返回 409(条目已被系统更新时,
提示用户查看新内容再决定)。

## 3. Testing

- API:CRUD 权限、分页筛选、乐观锁冲突 409、删除后注入范围立即排除、
  幂等删除。
- consolidator 交互:不复活已删除条目;系统更新后"曾被手动修改"标记
  仍在。
- UI:面板列表/筛选/搜索、编辑冲突提示、检查器条目跳转定位。
