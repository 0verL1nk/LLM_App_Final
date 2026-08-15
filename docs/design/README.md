# PaperSage UI 设计稿(OpenPencil 工作流)

此目录存放 PaperSage 前端 UI/UX 的设计产物,工作流:先用 OpenPencil 出设计稿,确认后再开发。

## 产物约定

- `<name>.html` — 设计源稿(内联样式,浏览器直接打开即最终视觉)
- `<name>.png` — 渲染快照(用于评审/PR 引用)
- `<name>.fig` — OpenPencil 可编辑文档(可用 OpenPencil 桌面版/Web 版打开继续编辑)

## 环境

- OpenPencil MCP 已注册到 Claude Code(user scope,`openpencil-mcp`),会话启动后工具以
  `mcp__open-pencil__` 前缀可用,优先用 MCP 工具直接建模。
- CLI 兜底:`@open-pencil/cli` 的 `import/export`(需 Bun 运行时)。截至 0.14.0 的已知问题:
  - `@open-pencil/mcp` 等包的 `exports` 含指向未发布 `src/` 的 `bun` 条件,Bun 下解析失败,
    需本地剥离 `bun` 条件后使用;
  - 无头 HTML import 不计算 CSS 布局,几何会塌到原点,只适合取颜色/字体/层级;
  - Windows 下 canvaskit-wasm 的 PNG 导出路径损坏,SVG 可导但受上条限制。
  结论:HEADLESS 路径只做格式转换,MCP/桌面端的建模工具才是主要设计入口。

## account-menu(v1.4.4)

合并重复设置入口后的账户区设计:侧边栏底部不再有独立"设置"导航项,
用户下拉内保留唯一"设置"入口(本地/云端模式选择 + 说明文案)。对应实现见 PR #100。
