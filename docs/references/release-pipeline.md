# 发布流水线

来源：AGENTS.md §7.1（规范本体）、`Makefile`、`.github/workflows/`。本文是速查蒸馏；
规则冲突时以 AGENTS.md 为准。

## 合并与提交

- **squash-only**：仓库设置已强制；PR 一律 squash merge，提交标题取 PR 标题、正文留空。
- **PR 标题必须符合 Conventional Commits**（`feat:`/`fix:`/`chore:`/`docs:`…）：
  squash 后它就是 main 上的提交，也是 changelog 的唯一来源。merge commit 会让
  release-please 把 PR 标题和原提交各记一次，造成 changelog 重复——这是禁 merge 的根因。

## 版本推进

- **版本号只由 release-please 推进**（`release-please.yml`，push main 触发）。禁止手动改
  `CHANGELOG.md`、`.release-please-manifest.json`、`agent/__init__.py`、`web/package.json`
  的版本；禁止手动创建/推送 `v*` tag——tag 推送即触发三平台自动打包
  （`desktop-release.yml`：Windows NSIS / macOS DMG / Linux AppImage+deb；`publish.yml`
  同时向 PyPI 发布）。
- **`release-as` 钉子不过夜**：仅在紧急指定版本号时添加，对应发布 PR 合并后的下一个
  PR 必须移除；残留钉子会让发布 PR 反复提议已存在的版本号，合并即撞 tag。
- **发布 PR 由 Release Train 定时合并**（`release-train.yml`，工作日 01:00 UTC）；
  紧急手动合并前必须核对目标版本号大于最新已存在 tag。

## 卡死急救：`autorelease: pending` 标签

release-please 在发布 PR 上维护 `autorelease: pending` 标签，打正式 release 时应自动
移除。若标签卡死（发布 PR 反复重生、release 不落）：**删除该标签后重跑
`Prepare Release` workflow**。1.4.3 事故即此病症——标签未清导致版本反复提议、合并撞
tag。恢复后检查 CHANGELOG 与 manifest 未被双写。

## 热修流程

1. 从 `origin/main` 切 `fix/*` 分支。
2. 修复 + **必须补回归测试**（AGENTS.md §6.3）。
3. squash merge 进 main。
4. 等待 Prepare Release 生成 patch 版本发布 PR，核对版本号后合并发布。
5. tag 自动触发三平台打包与 PyPI 发布；桌面端另见
   [../architecture/desktop-release.md](../architecture/desktop-release.md) 与 GPU 包开关
   `PAPERSAGE_DESKTOP_GPU`（[../architecture/desktop-ocr-packaging.md](../architecture/desktop-ocr-packaging.md)）。

## 本地检查入口

`make check`（lint-core + web 门禁 + 单测 + spec-validate）；完整离线 CI 等价
`make ci`。桌面打包本地入口：`make desktop-package-win[-gpu]`。
