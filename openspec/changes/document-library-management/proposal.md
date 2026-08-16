# Document Library Management(删除 / 重命名 / 全文阅读)

## Why

资料库当前只有"上传 + 状态 + 失败重试"。用户无法删除一份误传或不再需要的
资料(本地优先产品里这是隐私预期),无法重命名(上传时的文件名往往不是研究
语境里的称呼),也没有任何全文阅读入口——预览只存在于"证据定位"弹窗里,
想通读一篇论文必须回到外部工具,研究工作台的闭环断在"读"这一步。

## What Changes

1. **删除资料**:新增 `DELETE /documents/{doc_uid}`,立即从检索范围移除并
   **清除全部派生物**(LanceDB chunks、页面图、OCR 产物、原始文件)。历史
   消息中的引用降级为"文档已删除"占位,不再可打开内容——不保留可回看的
   软删除残留,删除即数据消失。
2. **重命名资料**:新增 `PATCH /documents/{doc_uid}` 修改标题;展示层
   (引用 chip、证据卡、检索范围)统一显示当前标题,不回写历史消息快照。
3. **全文阅读器**:资料库与证据预览可打开分页阅读视图。复用现有服务端
   页图管线(`/documents/{doc}/preview/{page}`,PDF/Office/图片/TXT 已统一
   转换为页面),提供页码导航、总页数、适应宽度、从证据引用深链跳转到
   指定页并叠加 OCR 高亮。不引入 pdf.js。
4. 资料库列表增加行内操作(打开阅读、重命名、删除带确认与影响提示)。

## Non-goals

- 不做全文内搜索、批注、页内文本选择复制(OCR 文本层属后续增强)。
- 不做批量删除/文件夹层级;一次一份。
- 不做软删除/回收站——本地单用户产品,删除应立即且彻底,避免"删了还在"
   的信任问题(与云端多租户的软删除理由不同)。
- 不改动 RAG 索引管线与证据坐标格式;阅读器只消费既有 preview 管线。
- 不迁移历史消息中的文档名快照。

## Impact

- Backend:`agent/adapters/sqlite/document_repository.py` 与
  `rag_ingestion_repository`(删除级联)、LanceDB vector_store 删除接口、
  FastAPI 文档路由、检索范围计算(已按 active 过滤,删除后自然出局)。
- Web:library-page 行内操作、新的分页阅读器组件(服务端页图 + SVG 高亮
  复用 evidence-preview 逻辑)、evidence chip/卡片的"已删除文档"状态。
- Docs:README 能力表、API 文档。
