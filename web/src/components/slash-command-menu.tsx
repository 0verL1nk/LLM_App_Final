import { Sparkles, Terminal } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react"

import { cn } from "@/lib/utils"
import {
  detectSlashTrigger,
  filterSlashCommands,
  type SlashCommandDef,
  type SlashCommandKind,
  type SlashTriggerHit,
} from "@/lib/slash-commands"

export interface UseSlashCommandMenuOptions {
  /** Current textarea value (controlled). */
  value: string
  /** Current textarea caret (selectionStart), refreshed by the composer. */
  caret: number
  /** Controlled setter used for completions and Enter cleanup. */
  setInput: (value: string) => void
  /** Restores the textarea caret after an in-place completion. */
  restoreCaret: (position: number) => void
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
  dismiss: () => void
  /** Pointer pick: executes a leading trigger, completes an inline one. */
  select: (index: number) => void
  handleKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

function hitKey(hit: SlashTriggerHit | null): string | null {
  return hit === null ? null : `${hit.span.start}:${hit.token}`
}

/**
 * Keyboard-driven slash command completion attached to the chat textarea,
 * following DeepSeek Harness's input-trigger model: the trigger is detected
 * at the caret anywhere in the draft ("帮我 /sum" opens the menu), Tab and
 * Space complete the token in place by replacing only its span, Enter
 * executes a leading command (or completes an inline one), and Esc dismisses
 * until the token changes. IME composition is never intercepted.
 */
export function useSlashCommandMenu(options: UseSlashCommandMenuOptions): SlashCommandMenuState {
  const { value, caret, setInput, restoreCaret, commands, onExecute } = options
  const [activeIndex, setActiveIndex] = useState(0)
  const [dismissedKey, setDismissedKey] = useState<string | null>(null)
  const [lastKey, setLastKey] = useState<string | null>(() => null)

  const hit = detectSlashTrigger(value, caret)
  const currentKey = hitKey(hit)
  // Reset transient state during render whenever the trigger token moves or
  // changes, so selection and dismissal never leak across edits.
  if (lastKey !== currentKey) {
    setLastKey(currentKey)
    setActiveIndex(0)
    setDismissedKey(null)
  }

  const filtered = useMemo(
    () => (hit === null ? [] : filterSlashCommands(commands, hit.token)),
    [commands, hit],
  )
  const safeIndex = filtered.length === 0 ? 0 : Math.min(activeIndex, filtered.length - 1)
  const open = hit !== null && currentKey !== dismissedKey

  const completeInPlace = useCallback(
    (target: SlashTriggerHit, command: SlashCommandDef) => {
      const replacement = `/${command.name} `
      setInput(value.slice(0, target.span.start) + replacement + value.slice(target.span.end))
      restoreCaret(target.span.start + replacement.length)
    },
    [setInput, restoreCaret, value],
  )

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      if (!open || hit === null || event.nativeEvent.isComposing) return
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (!filtered.length) return
        event.preventDefault()
        const delta = event.key === "ArrowDown" ? 1 : -1
        setActiveIndex((current) => (current + delta + filtered.length) % filtered.length)
        return
      }
      if (event.key === "Escape") {
        event.preventDefault()
        setDismissedKey(currentKey)
        return
      }
      if (event.key === "Tab") {
        const active = filtered[safeIndex]
        if (!active) return
        event.preventDefault()
        completeInPlace(hit, active)
        return
      }
      if (event.key === " " && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
        // Space after an exact command name completes the token, dsh-style:
        // "/skills " leaves argument entry ready without dismissing the mode.
        const exact = commands.find(
          (command) => command.name.toLowerCase() === hit.token.toLowerCase(),
        )
        if (exact) {
          event.preventDefault()
          completeInPlace(hit, exact)
        }
        return
      }
      if (event.key === "Enter") {
        if (!filtered.length) return
        event.preventDefault()
        const active = filtered[safeIndex]
        if (!active) return
        if (hit.leading) {
          setInput("")
          onExecute(active)
          return
        }
        completeInPlace(hit, active)
      }
    },
    [open, hit, currentKey, filtered, safeIndex, commands, completeInPlace, setInput, onExecute],
  )

  const dismiss = useCallback(() => setDismissedKey(currentKey), [currentKey])

  const select = useCallback(
    (index: number) => {
      const command = filtered[index]
      if (!command || hit === null) return
      if (hit.leading) {
        setInput("")
        onExecute(command)
        return
      }
      completeInPlace(hit, command)
    },
    [filtered, hit, setInput, onExecute, completeInPlace],
  )

  return { open, filtered, activeIndex: safeIndex, setActiveIndex, dismiss, select, handleKeyDown }
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
  /** Closes the menu when the pointer lands outside the composer card. */
  onDismiss: () => void
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
 * all navigation state lives in useSlashCommandMenu. Clicks on the textarea
 * or composer chrome keep the menu open; clicks elsewhere dismiss it.
 */
export function SlashCommandMenu({ filtered, activeIndex, onHover, onSelect, onDismiss }: SlashCommandMenuProps) {
  const groups = groupByKind(filtered)
  const rootRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!(event.target instanceof Node)) return
      if (rootRef.current?.contains(event.target)) return
      if (event.target instanceof Element && event.target.closest("[data-slash-scope]")) return
      onDismiss()
    }
    document.addEventListener("pointerdown", onPointerDown, true)
    return () => document.removeEventListener("pointerdown", onPointerDown, true)
  }, [onDismiss])
  return (
    <div
      ref={rootRef}
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
        ↑↓ 选择 · Tab/空格 补全 · Enter 执行 · Esc 关闭
      </p>
    </div>
  )
}
