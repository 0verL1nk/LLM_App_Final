# 发布与 CI 排障手册(实战沉淀)

2026-08-23 高强度发版日沉淀。每一条都是当日真实撞墙,附验证过解法。

## 发布流水线(全链路)

```
合并功能 PR 到 main(squash)
  → release-please 自动开/更新 "chore(main): release X.Y.Z" PR
  → 合并该 PR
  → 手动 dispatch workflow "Publish Merged Version"(inputs: release_pr=PR 号)
  → 自动打 tag → desktop-release 构建 → Release 挂资产 + latest.yml
```

**撞过的墙:**

1. **squash 合并的标题决定版本号**:GitHub 默认取分支首个 commit 的标题作为 squash 标题——`feat` 分支若带着早期的 `fix` 提交,整包会被 release-please 归类为 patch(实例:#153 的 feat 被降级成 1.10.2)。合 feat PR 前检查 squash 标题,必要时在 merge 时显式指定。
2. **release PR 不会自动合并**:publish-version 必须**手动 dispatch**,遗忘这步 = tag 不出、包不发。
3. **GPU 测试运行会失败但正式 tag 构建正常**:带 `gpu=true` 的 workflow_dispatch 是测试运行;判断发布状态看 tag 触发的那次 desktop-release。

## 质量门(debt ratchet / 行数棘轮)

- `scripts/code_size_baseline.json` 登记超限遗留文件的**上限**,只许减不许增。
- **新文件超过 500 行直接拒绝**(无基线可用),拆文件是唯一解(实例:test_turn_engine 524 行 → 拆出 test_turn_component_parts)。
- **文件瘦身到限额以下后,必须删除对应基线条目**,否则报 "remove resolved entry"(实例:research-page 拆分后 588→366 行)。
- **main 会带伤合并**(红着合):每次开 PR 先看 `gh run list --workflow=quality.yml --branch main`,若 main 已红,先修 main 的问题(import 排序、类型错误、基线),你的 PR 才能绿。
- CI 的 ruff/ty 检查**跑的是 PR 分支头**(非 merge 预览):main 修好后需把 main 合进 PR 分支重跑。

## PR 操作的坑

- `gh pr edit` **没有 --head 参数**;REST `PATCH pulls/N {head}` 对本仓分支**也会被静默拒绝**。解法:把修好的提交**直接推到 PR 的原分支名**:`git push origin my-branch:original-pr-branch`。
- **陈旧 check 会一直显示失败**:`gh pr checks` 列出的是各 workflow 最新一次运行,推新提交后旧失败仍在列表里——以**新 commit 时间戳**的运行为准,`--watch` 等新运行完成。
- 2 秒内即失败的 `CodeQL` check 是初始化残留,真正的 `Analyze (python/go/js)` 全过即可合并。

## Git worktree 纪律(多会话并行)

- **worktree 之间会互相踩**:并行会话曾把主树 WIP 复制进我的 worktree、切换我 worktree 的分支、甚至把主树 checkout 到我建的分支上。症状:编辑成功后文件内容"凭空回退"、`git switch` 报 branch already used。
- 纪律:改完**立刻提交**(提交进对象库后免疫工作区覆盖);切分支前 `git status` 核对;发现污染先 `diff` 主树确认副本冗余再 `git checkout -- .`。
- 拿别人 worktree 里的分支:开自己的分支 + `git push origin mine:theirs-branch`,不动对方工作区。

## electron-updater 更新体积

- 差分下载(blockmap)**默认启用**;要求 `%LOCALAPPDATA%\<app>-updater\pending\` 里有上一个安装包 + blockmap 作基底——重装/清缓存后第一次必然全量。
- 本项目安装包 ~500MB,其中 ~90% 是 PyInstaller 后端,**每个版本都重新构建**(字节级必变)→ NSIS 固实压缩下差分效果有限。前端改动也要拖上后端重下。
- 可选优化方向(未做):CI 按后端源码哈希缓存后端构建产物,后端无变化时安装包差分缩到 MB 级;或彻底拆分后端为独立下载(GPU 包同款机制)。

## 其他实战坑

- **node:test + mock timers + async 链**:mock 计时器不冲刷微任务,`await tick()` 后断言异步结果会假阴性——每步 tick 后补 `await new Promise(r => setImmediate(r))`。
- **`uv run` 的 editable 安装指向主树**:在 worktree 跑测试须加 `PYTHONPATH=<worktree>`,否则导入的是主树代码(症状:改了代码测试结果不变)。
- **Windows 控制台 GBK**:`print` 中文/emoji 抛 UnicodeEncodeError——`python -X utf8` 或写文件中转。
- **锁失败的静默退出是黑洞**:单实例锁/单飞逻辑失败时必须留日志,否则"什么都没发生"无从排查(实例:更新重启竞态)。
