import { describe, expect, it } from "vitest"

import {
  BUILTIN_COMMANDS,
  BUILTIN_COMMAND_NAMES,
  detectSlashTrigger,
  expandSkillDirective,
  filterSlashCommands,
  resolveSlashSubmission,
  type SlashCommandDef,
} from "@/lib/slash-commands"

const commands: readonly SlashCommandDef[] = [
  { name: "skills", description: "列出可用技能", kind: "builtin" },
  { name: "compact", description: "压缩上下文", kind: "builtin" },
  { name: "summary", description: "总结论文要点", kind: "skill" },
]

const skillNames = new Set(["summary", "translation"])

describe("detectSlashTrigger", () => {
  it("detects a leading slash at the caret with its span", () => {
    expect(detectSlashTrigger("/", 1)).toEqual({
      token: "",
      span: { start: 0, end: 1 },
      leading: true,
    })
    expect(detectSlashTrigger("/su", 3)).toEqual({
      token: "su",
      span: { start: 0, end: 3 },
      leading: true,
    })
  })

  it("detects inline triggers after whitespace but not mid-word", () => {
    expect(detectSlashTrigger("帮我 /sum", 7)).toEqual({
      token: "sum",
      span: { start: 3, end: 7 },
      leading: false,
    })
    expect(detectSlashTrigger("a/b", 3)).toBeNull()
    expect(detectSlashTrigger("word/su", 7)).toBeNull()
  })

  it("keeps slashes inside URLs and double slashes dead", () => {
    expect(detectSlashTrigger("看 https://example.com/paper", 27)).toBeNull()
    expect(detectSlashTrigger("path//tmp", 9)).toBeNull()
  })

  it("stops the token at whitespace and before the caret", () => {
    expect(detectSlashTrigger("/summary 参数", 5)).toEqual({
      token: "summ",
      span: { start: 0, end: 5 },
      leading: true,
    })
    expect(detectSlashTrigger("/summary ", 10)).toBeNull()
    expect(detectSlashTrigger("/su", 0)).toBeNull()
  })

  it("allows triggers after punctuation but not after a scheme colon", () => {
    expect(detectSlashTrigger("结论、/sum", 7)).toEqual({
      token: "sum",
      span: { start: 3, end: 7 },
      leading: false,
    })
    // "x:/y" reads as a URL scheme separator and stays plain text (dsh rule).
    expect(detectSlashTrigger("结论:/sum", 7)).toBeNull()
  })

  it("treats a trigger after leading spaces as leading", () => {
    expect(detectSlashTrigger("  /sum", 6)?.leading).toBe(true)
  })
})

describe("filterSlashCommands", () => {
  it("returns everything for an empty token with builtins first", () => {
    expect(filterSlashCommands(commands, "")).toEqual(commands)
  })

  it("matches prefixes case-insensitively and ranks them first", () => {
    const ranked = filterSlashCommands(commands, "su")
    expect(ranked.map((item) => item.name)).toEqual(["summary"])
  })

  it("keeps substring and description matches after prefix matches", () => {
    const withSkill: readonly SlashCommandDef[] = [
      { name: "skills", description: "列出技能", kind: "builtin" },
      { name: "summarize", description: "总结", kind: "skill" },
      { name: "reset", description: "重置 summary 会话状态", kind: "builtin" },
    ]
    const ranked = filterSlashCommands(withSkill, "sum")
    expect(ranked.map((item) => item.name)).toEqual(["summarize", "reset"])
  })

  it("drops non-matching commands", () => {
    expect(filterSlashCommands(commands, "zzz")).toEqual([])
  })
})

describe("resolveSlashSubmission", () => {
  it("routes exact builtin commands with trailing arguments", () => {
    expect(resolveSlashSubmission("/skills", skillNames)).toEqual({
      type: "command",
      name: "skills",
      args: "",
    })
    expect(resolveSlashSubmission("/compact  now", skillNames)).toEqual({
      type: "command",
      name: "compact",
      args: "now",
    })
  })

  it("routes known skill names with task arguments", () => {
    expect(resolveSlashSubmission("/summary 总结这篇论文", skillNames)).toEqual({
      type: "skill",
      name: "summary",
      args: "总结这篇论文",
    })
  })

  it("falls back to a plain prompt for anything else", () => {
    expect(resolveSlashSubmission("/foobar 参数", skillNames)).toEqual({
      type: "prompt",
      prompt: "/foobar 参数",
    })
    expect(resolveSlashSubmission("普通问题 /skills", skillNames)).toEqual({
      type: "prompt",
      prompt: "普通问题 /skills",
    })
  })
})

describe("expandSkillDirective", () => {
  it("wraps task arguments in an explicit use_skill instruction", () => {
    const directive = expandSkillDirective("summary", "总结这篇论文")
    expect(directive).toContain("use_skill")
    expect(directive).toContain("summary")
    expect(directive).toContain("总结这篇论文")
  })

  it("asks for usage guidance when no task is provided", () => {
    const directive = expandSkillDirective("summary", "")
    expect(directive).toContain("介绍")
    expect(directive).toContain("summary")
  })
})

describe("builtin registry", () => {
  it("ships the full builtin command set with unique names", () => {
    const names = BUILTIN_COMMANDS.map((item) => item.name)
    expect(new Set(names).size).toBe(names.length)
    for (const expected of ["skills", "compact", "help", "documents", "memory", "model", "new", "rename"]) {
      expect(BUILTIN_COMMAND_NAMES.has(expected)).toBe(true)
    }
  })
})
