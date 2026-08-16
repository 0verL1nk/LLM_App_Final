import { useCallback, useMemo } from "react"

import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputProvider,
  PromptInputSubmit,
  PromptInputTextarea,
  usePromptInputController,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input"
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion"
import { ContextCompositionCard } from "@/components/context-composition"
import { ModeSelector, type ExecutionMode } from "@/components/mode-selector"
import { SlashCommandMenu, useSlashCommandMenu } from "@/components/slash-command-menu"
import type { SessionContextUsage } from "@/lib/context-usage"
import { useSkills } from "@/lib/queries"
import {
  BUILTIN_COMMANDS,
  expandSkillDirective,
  resolveSlashSubmission,
  type SlashCommandDef,
} from "@/lib/slash-commands"

export interface ResearchComposerProps {
  inputDisabled: boolean
  submitStatus: "ready" | "submitted"
  suggestions: string[]
  showSuggestions: boolean
  executionMode: ExecutionMode
  onExecutionModeChange: (mode: ExecutionMode) => void
  modeDisabled: boolean
  contextUsage: SessionContextUsage | null
  onPromptSubmit: (prompt: string) => void
  onCommand: (command: string, args: string) => void
}

/**
 * Chat input area with Codex-style slash command completion: typing "/" opens
 * a keyboard-driven command popup (builtins + project skills), Enter executes
 * the highlighted entry, and submissions are routed to commands, skill
 * directives, or plain prompts.
 */
export function ResearchComposer(props: ResearchComposerProps) {
  return (
    <PromptInputProvider>
      <ComposerInner {...props} />
    </PromptInputProvider>
  )
}

function ComposerInner({
  inputDisabled,
  submitStatus,
  suggestions,
  showSuggestions,
  executionMode,
  onExecutionModeChange,
  modeDisabled,
  contextUsage,
  onPromptSubmit,
  onCommand,
}: ResearchComposerProps) {
  const controller = usePromptInputController()
  const skills = useSkills()
  const skillCommands = useMemo<SlashCommandDef[]>(
    () =>
      (skills.data ?? []).map((skill) => ({
        name: skill.name,
        description: skill.description,
        kind: "skill" as const,
      })),
    [skills.data],
  )
  const commands = useMemo(() => [...BUILTIN_COMMANDS, ...skillCommands], [skillCommands])
  const skillNames = useMemo(() => new Set(skillCommands.map((item) => item.name)), [skillCommands])

  const executeFromMenu = useCallback(
    (command: SlashCommandDef) => {
      if (command.kind === "builtin") {
        onCommand(command.name, "")
        return
      }
      onPromptSubmit(expandSkillDirective(command.name, ""))
    },
    [onCommand, onPromptSubmit],
  )
  const menu = useSlashCommandMenu({
    value: controller.textInput.value,
    setInput: controller.textInput.setInput,
    commands,
    onExecute: executeFromMenu,
  })
  const selectFromMenu = useCallback(
    (index: number) => {
      const command = menu.filtered[index]
      if (!command) return
      controller.textInput.setInput("")
      executeFromMenu(command)
    },
    [menu.filtered, controller.textInput, executeFromMenu],
  )
  const handleSubmit = useCallback(
    ({ text }: PromptInputMessage) => {
      const resolved = resolveSlashSubmission(text, skillNames)
      if (resolved.type === "command") {
        onCommand(resolved.name, resolved.args)
        return
      }
      if (resolved.type === "skill") {
        onPromptSubmit(expandSkillDirective(resolved.name, resolved.args))
        return
      }
      onPromptSubmit(resolved.prompt)
    },
    [onCommand, onPromptSubmit, skillNames],
  )

  return (
    <div className="mx-auto w-full max-w-3xl">
      {showSuggestions && suggestions.length > 0 ? (
        <Suggestions className="mb-3">
          {suggestions.map((suggestion) => (
            <Suggestion key={suggestion} suggestion={suggestion} onClick={onPromptSubmit} />
          ))}
        </Suggestions>
      ) : null}
      <div className="relative">
        {menu.open ? (
          <SlashCommandMenu
            filtered={menu.filtered}
            activeIndex={menu.activeIndex}
            onHover={menu.setActiveIndex}
            onSelect={selectFromMenu}
          />
        ) : null}
        <PromptInput onSubmit={handleSubmit}>
          <PromptInputBody>
            <PromptInputTextarea
              aria-label="消息输入框"
              disabled={inputDisabled}
              placeholder="询问论文、比较方法，或输入 / 使用命令…"
              onKeyDown={menu.handleKeyDown}
            />
          </PromptInputBody>
          <PromptInputFooter>
            <span className="text-[11px] text-muted-foreground">
              Enter 发送 · Shift + Enter 换行 · / 唤起命令 · 回答可能需要核对原始证据
            </span>
            <div className="flex items-center gap-1">
              <ModeSelector
                value={executionMode}
                onChange={onExecutionModeChange}
                disabled={modeDisabled}
              />
              {contextUsage ? <ContextCompositionCard usage={contextUsage} /> : null}
              <PromptInputSubmit disabled={inputDisabled} status={submitStatus} />
            </div>
          </PromptInputFooter>
        </PromptInput>
      </div>
    </div>
  )
}
