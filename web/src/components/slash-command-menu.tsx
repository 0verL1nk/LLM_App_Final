import { Sparkles, Terminal } from "lucide-react"
import { useCallback, useMemo, useState, type KeyboardEvent } from "react"

import { cn } from "@/lib/utils"
import {
  filterSlashCommands,
  parseSlashToken,
  type SlashCommandDef,
  type SlashCommandKind,
} from "@/lib/slash-commands"

export interface UseSlashCommandMenuOptions {
  /** Current textarea value (controlled). */
  value: string
  /** Controlled setter used for Tab completion and Enter cleanup. */
  setInput: (value: string) => void
  /** Full command registry; builtins are expected before skills. */
  commands: readonly SlashCommandDef[]
  /** Invoked when the user executes the highlighted command. */
  onExecute: (command: SlashCommandDef) => void
}

export interface SlashCommandMenuState {
  open: boolean
  filtered: SlashCommandDef[]
  activeIndex: number
  setActiveIndex: (index: number) => void
  handleKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

/**
 * Keyboard-driven slash command completion attached to the chat textarea:
 * ↑/↓ move, Tab completes, Enter executes, Esc dismisses until the token
 * changes. IME composition is never intercepted.
 */
export function useSlashCommandMenu(options: UseSlashCommandMenuOptions): SlashCommandMenuState {
  const { value, setInput, commands, onExecute } = options
  const [activeIndex, setActiveIndex] = useState(0)
  const [dismissedToken, setDismissedToken] = useState<string | null>(null)
  const [lastToken, setLastToken] = useState<string | null>(() => null)

  const token = parseSlashToken(value)
  // Reset transient state during render whenever the slash token changes,
  // so selection and dismissal never leak across edits.
  if (lastToken !== token) {
    setLastToken(token)
    setActiveIndex(0)
    setDismissedToken(null)
  }

  const filtered = useMemo(
    () => (token === null ? [] : filterSlashCommands(commands, token)),
    [commands, token],
  )
  const safeIndex = filtered.length === 0 ? 0 : Math.min(activeIndex, filtered.length - 1)
  const open = token !== null && token !== dismissedToken

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (!open || event.nativeEvent.isComposing) return
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (!filtered.length) return
        event.preventDefault()
        const delta = event.key === "ArrowDown" ? 1 : -1
        setActiveIndex((current) => (current + delta + filtered.length) % filtered.length)
        return
      }
      if (event.key === "Escape") {
        event.preventDefault()
        setDismissedToken(token)
        return
      }
      if (event.key === "Tab") {
        const active = filtered[safeIndex]
        if (!active) return
        event.preventDefault()
        setInput(`/${active.name} `)
        return
      }
      if (event.key === "Enter") {
        if (!filtered.length) return
        event.preventDefault()
        const active = filtered[safeIndex]
        if (active) {
          setInput("")
          onExecute(active)
        }
      }
    },
    [open, filtered, safeIndex, token, setInput, onExecute],
  )

  return { open, filtered, activeIndex: safeIndex, setActiveIndex, handleKeyDown }
}

const GROUP_LABELS: Record<SlashCommandKind, string> = {
  builtin: "命令",
  skill: "技能",
}

export interface SlashCommandMenuProps {
  filtered: SlashCommandDef[]
  activeIndex: number
  onHover: (index: number) => void
  onSelect: (index: number) => void
}

interface MenuGroup {
  kind: SlashCommandKind
  items: Array<{ command: SlashCommandDef; index: number }>
}

function groupByKind(filtered: SlashCommandDef[]): MenuGroup[] {
  const groups: MenuGroup[] = []
  for (const [index, command] of filtered.entries()) {
    const current = groups.at(-1)
    if (current && current.kind === command.kind) {
      current.items.push({ command, index })
    } else {
      groups.push({ kind: command.kind, items: [{ command, index }] })
    }
  }
  return groups
}

/**
 * Popup listing slash commands above the input; purely presentational,
 * all navigation state lives in useSlashCommandMenu.
 */
export function SlashCommandMenu({ filtered, activeIndex, onHover, onSelect }: SlashCommandMenuProps) {
  const groups = groupByKind(filtered)
  return (
    <div
      role="listbox"
      aria-label="斜杠命令"
      className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border bg-popover/95 shadow-lg backdrop-blur"
    >
      <div className="max-h-64 overflow-y-auto p-1">
        {filtered.length === 0 ? (
          <p className="px-2.5 py-2 text-sm text-muted-foreground">没有匹配的命令</p>
        ) : (
          groups.map((group) => (
            <div key={group.kind}>
              <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium text-muted-foreground">
                {GROUP_LABELS[group.kind]}
              </p>
              {group.items.map(({ command, index }) => (
                <div
                  key={`${command.kind}:${command.name}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => onHover(index)}
                  onClick={() => onSelect(index)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm outline-none",
                    index === activeIndex && "bg-muted",
                  )}
                >
                  {command.kind === "builtin" ? (
                    <Terminal className="size-3.5 shrink-0 text-muted-foreground" />
                  ) : (
                    <Sparkles className="size-3.5 shrink-0 text-muted-foreground" />
                  )}
                  <span className="font-mono text-[13px] text-primary">/{command.name}</span>
                  <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                    {command.description}
                  </span>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
      <p className="border-t px-2.5 py-1.5 text-[11px] text-muted-foreground">
        ↑↓ 选择 · Tab 补全 · Enter 执行 · Esc 关闭
      </p>
    </div>
  )
}
