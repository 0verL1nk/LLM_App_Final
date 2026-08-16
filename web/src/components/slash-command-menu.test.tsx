// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { useState, type KeyboardEvent } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  SlashCommandMenu,
  useSlashCommandMenu,
} from "@/components/slash-command-menu"
import type { SlashCommandDef } from "@/lib/slash-commands"

const commands: readonly SlashCommandDef[] = [
  { name: "skills", description: "列出可用技能及其用途", kind: "builtin" },
  { name: "compact", description: "压缩会话上下文", kind: "builtin" },
  { name: "summary", description: "总结论文要点", kind: "skill" },
]

function Harness({ onExecute }: { onExecute: (command: SlashCommandDef) => void }) {
  const [value, setValue] = useState("")
  const menu = useSlashCommandMenu({ value, setInput: setValue, commands, onExecute })
  const execute = (index: number) => {
    const command = menu.filtered[index]
    if (command) {
      setValue("")
      onExecute(command)
    }
  }
  return (
    <div className="relative">
      {menu.open ? (
        <SlashCommandMenu
          filtered={menu.filtered}
          activeIndex={menu.activeIndex}
          onHover={menu.setActiveIndex}
          onSelect={execute}
        />
      ) : null}
      <textarea
        aria-label="消息输入框"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => menu.handleKeyDown(event)}
      />
    </div>
  )
}

function typeValue(value: string) {
  fireEvent.change(screen.getByLabelText("消息输入框"), { target: { value } })
}

describe("SlashCommandMenu", () => {
  afterEach(cleanup)

  it("opens above the input when the value starts with a slash", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("/")

    const listbox = screen.getByRole("listbox")
    expect(listbox).toBeTruthy()
    expect(screen.getByText("/skills")).toBeTruthy()
    expect(screen.getByText("/summary")).toBeTruthy()
    expect(screen.getByText("命令")).toBeTruthy()
    expect(screen.getByText("技能")).toBeTruthy()
  })

  it("filters while typing and resets to the first entry", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("/su")

    expect(screen.getByText("/summary")).toBeTruthy()
    expect(screen.queryByText("/skills")).toBeNull()
  })

  it("moves the highlighted option with arrow keys", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("/")
    const textarea = screen.getByLabelText("消息输入框")

    fireEvent.keyDown(textarea, { key: "ArrowDown" })

    const options = screen.getAllByRole("option")
    expect(options.map((option) => option.getAttribute("aria-selected"))).toEqual([
      "false",
      "true",
      "false",
    ])
  })

  it("completes the highlighted command with Tab", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("/sum")
    const textarea = screen.getByLabelText("消息输入框") as HTMLTextAreaElement

    fireEvent.keyDown(textarea, { key: "Tab" })

    expect(textarea.value).toBe("/summary ")
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("executes the highlighted command with Enter", () => {
    const onExecute = vi.fn()
    render(<Harness onExecute={onExecute} />)
    typeValue("/sum")
    const textarea = screen.getByLabelText("消息输入框") as HTMLTextAreaElement

    fireEvent.keyDown(textarea, { key: "Enter" })

    expect(onExecute).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ name: "summary", kind: "skill" }),
    )
    expect(textarea.value).toBe("")
  })

  it("closes on Escape and reopens when the token changes", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("/")
    const textarea = screen.getByLabelText("消息输入框")

    fireEvent.keyDown(textarea, { key: "Escape" })
    expect(screen.queryByRole("listbox")).toBeNull()

    typeValue("/c")
    expect(screen.getByRole("listbox")).toBeTruthy()
  })

  it("shows an empty state and lets Enter fall through when nothing matches", () => {
    const onExecute = vi.fn()
    render(<Harness onExecute={onExecute} />)
    typeValue("/zzz")
    const textarea = screen.getByLabelText("消息输入框")

    expect(screen.getByText("没有匹配的命令")).toBeTruthy()
    fireEvent.keyDown(textarea, { key: "Enter" })
    expect(onExecute).not.toHaveBeenCalled()
  })

  it("stays closed for plain prompts", () => {
    render(<Harness onExecute={vi.fn()} />)
    typeValue("帮我总结这篇论文")

    expect(screen.queryByRole("listbox")).toBeNull()
  })
})
