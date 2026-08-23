export type SlashCommandKind = "builtin" | "skill"

export interface SlashCommandDef {
  name: string
  description: string
  kind: SlashCommandKind
}

export const BUILTIN_COMMANDS: readonly SlashCommandDef[] = [
  { name: "skills", description: "列出可用技能及其用途", kind: "builtin" },
  { name: "compact", description: "压缩会话上下文，保留近期消息与摘要", kind: "builtin" },
  { name: "help", description: "查看全部命令与用法", kind: "builtin" },
  { name: "documents", description: "查看项目资料清单与处理状态", kind: "builtin" },
  { name: "memory", description: "查看项目记忆与稳定偏好", kind: "builtin" },
  { name: "model", description: "查看当前模型配置", kind: "builtin" },
  { name: "new", description: "新建探索会话并切换过去", kind: "builtin" },
  { name: "rename", description: "重命名当前会话（/rename 新名称）", kind: "builtin" },
] as const

export const BUILTIN_COMMAND_NAMES: ReadonlySet<string> = new Set(
  BUILTIN_COMMANDS.map((command) => command.name),
)

export interface SlashTriggerHit {
  /** Token typed between the slash and the caret ("" for a lone slash). */
  token: string
  /** Draft range occupied by the trigger token: [start, caret). */
  span: { start: number; end: number }
  /** True when the slash sits at the draft's first non-space character. */
  leading: boolean
}

const WORD_CHAR = /[\p{L}\p{N}_]/u
const WHITESPACE = /\s/u

/**
 * Detects the slash-command token under the caret, anywhere in the draft —
 * not only at the start. Detection model ported from DeepSeek Harness's
 * ui-input-trigger core: scan backward from the caret, stop at whitespace,
 * and require a word boundary before the slash so "a/b", URL paths, and "//"
 * stay plain text. Only `leading` hits execute as commands on Enter; inline
 * hits complete in place, mirroring dsh's command-vs-reference split.
 */
export function detectSlashTrigger(draft: string, caret: number): SlashTriggerHit | null {
  for (let i = Math.min(caret, draft.length) - 1; i >= 0; i--) {
    const ch = draft.charAt(i)
    if (WHITESPACE.test(ch)) return null
    if (ch !== "/") continue
    if (i > 0) {
      const prev = draft.charAt(i - 1)
      // "word/" or "user@host/x" style: the slash is ordinary text.
      if (WORD_CHAR.test(prev)) continue
      // URL carve-outs: second slash of "//" and the path slash in "scheme://".
      if (prev === "/") continue
      if (prev === ":" && i >= 2 && !WHITESPACE.test(draft.charAt(i - 2))) continue
    }
    return {
      token: draft.slice(i + 1, caret),
      span: { start: i, end: caret },
      leading: draft.search(/\S/) === i,
    }
  }
  return null
}

/**
 * Filters commands for the popup: prefix matches rank first, then substring
 * matches on the name, then description matches; original order is kept
 * within each tier so builtins stay ahead of skills.
 */
export function filterSlashCommands(
  commands: readonly SlashCommandDef[],
  token: string,
): SlashCommandDef[] {
  const normalized = token.trim().toLowerCase()
  if (!normalized) return [...commands]
  return commands
    .map((command) => {
      const name = command.name.toLowerCase()
      const description = command.description.toLowerCase()
      if (name.startsWith(normalized)) return { command, rank: 0 }
      if (name.includes(normalized)) return { command, rank: 1 }
      if (description.includes(normalized)) return { command, rank: 2 }
      return null
    })
    .filter((entry): entry is { command: SlashCommandDef; rank: number } => entry !== null)
    .sort((a, b) => a.rank - b.rank)
    .map((entry) => entry.command)
}

export type SlashSubmission =
  | { type: "command"; name: string; args: string }
  | { type: "skill"; name: string; args: string }
  | { type: "prompt"; prompt: string }

/**
 * Classifies a submitted input line: exact builtin command, known skill, or a
 * plain prompt. Only a leading slash is honored, mirroring parseSlashToken.
 */
export function resolveSlashSubmission(value: string, skillNames: ReadonlySet<string>): SlashSubmission {
  const trimmed = value.trim()
  if (!trimmed.startsWith("/")) return { type: "prompt", prompt: trimmed }
  const name = trimmed.slice(1).split(/\s+/, 1)[0] ?? ""
  if (!name) return { type: "prompt", prompt: trimmed }
  const args = trimmed.slice(1 + name.length).trim()
  if (BUILTIN_COMMAND_NAMES.has(name)) return { type: "command", name, args }
  if (skillNames.has(name)) return { type: "skill", name, args }
  return { type: "prompt", prompt: trimmed }
}

/**
 * Deterministic prompt expansion for explicit skill invocation; the agent
 * carries the matching use_skill tool, so the directive stays literal.
 */
export function expandSkillDirective(name: string, args: string): string {
  const task = args.trim()
  if (task) {
    return `请调用 use_skill 工具，使用技能「${name}」完成以下任务：\n\n${task}`
  }
  return `请调用 use_skill 工具，介绍技能「${name}」的用法、适用场景与操作步骤。`
}
