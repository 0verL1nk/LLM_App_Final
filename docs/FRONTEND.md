# web/ 前端约定

Vite + React + TypeScript 独立客户端。UI/UX 层面约定见 [DESIGN.md](DESIGN.md)；
信息架构与产品模型见 [architecture/web-application.md](architecture/web-application.md)。
web 只经 HTTP 契约访问后端，禁止导入 Python 业务模块或复制后端状态机（AGENTS.md §2）。

## 路由（TanStack Router）

- 路由集中在 `web/src/router.tsx`：`createRootRoute` + `createRoute`，页面用
  `lazyRouteComponent(() => import("@/pages/…"), "NamedExport")` 懒加载。
- 可导航状态（选中项目/会话）必须活在 URL 里，不允许藏在组件单例中。
- 新页面：在 `src/pages` 建路由级组件 + router.tsx 注册一行，不新增路由库或导航方案。

## 数据（TanStack Query + zod 契约）

- 远端数据、缓存失效、轮询、变更全部走 Query；本地仅 UI 状态用 Zustand
  （主题、移动导航、检查器标签）。
- API 调用统一经 `web/src/lib/api.ts` 的 `api(path, schema, init)`：响应体按
  `envelope.data` 解包并强制 `schema.parse`——zod schema 是唯一契约源，手写
  `fetch + any` 不合规范。上传用 `upload()`，SSE 用 `consumeEventStream()`。
- 契约 schema 放 `src/lib/schemas.ts`（与后端 `api/schemas.py` 对应），query 组合放
  `src/lib/queries.ts`。

## SSE 断线重放恢复

- 会话事件流基于 durable Run 事件序号：断线后带 `afterSeq` 游标重放
  （`api/routes.py` 的 SSE 端点 + `web/src/lib/live-run.ts`）。
- 客户端按序应用事件、按 `surfaceId`/part ID 幂等合并，重复事件不产生重复 UI；
  页面级轮询只在无 SSE 语义的端点上使用（如评测运行快照）。

## 状态来自服务端事实

- 禁止 mock 运行时事实：进度、任务队列、context 用量、证据来源都必须来自 API
  （AGENTS.md §3.16）。前端可以包装展示，不可以发明数据。
- 测试不得以 mock 数据冒充服务端行为验证 UI 逻辑；纯逻辑抽到 `src/lib` 并配
  `*.test.ts` 单测。

## 组件职责分层

- `src/pages/`：路由级组合——组装 sections、拉数据、处理页面级状态，不写展示细节。
- `src/components/`：展示与交互组件——props 进、事件出，不直接发请求、不持有远端缓存。
- `src/lib/`：纯逻辑——schema、query、SSE 解析、格式化；可单测的代码放这里。
- 跨组件共享的 UI 状态走 Zustand store；不允许为绕过分层把请求塞进组件工具函数。
