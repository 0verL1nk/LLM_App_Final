// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ResearchComposer } from "@/components/research-composer"

const fetchMock = vi.fn()

function renderComposer(props: Partial<Parameters<typeof ResearchComposer>[0]> = {}) {
  const onPromptSubmit = vi.fn()
  const onCommand = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ResearchComposer
        inputDisabled={false}
        submitStatus="ready"
        suggestions={[]}
        showSuggestions={false}
        executionMode="auto"
        onExecutionModeChange={vi.fn()}
        modeDisabled={false}
        contextUsage={null}
        onPromptSubmit={onPromptSubmit}
        onCommand={onCommand}
        {...props}
      />
    </QueryClientProvider>,
  )
  return { onPromptSubmit, onCommand }
}

/** Types a value into the composer with the caret at its end. */
function typeValue(value: string) {
  const textarea = screen.getByLabelText("消息输入框") as HTMLTextAreaElement
  fireEvent.change(textarea, { target: { value } })
  Object.assign(textarea, { selectionStart: value.length, selectionEnd: value.length })
  fireEvent.keyUp(textarea, { key: "a" })
}

describe("ResearchComposer", () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ data: [{ name: "summary", description: "总结论文要点" }] }),
    })
    vi.stubGlobal("fetch", fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it("lists builtin commands and fetched skills in the popup", async () => {
    renderComposer()
    typeValue("/")

    expect(screen.getByText("/skills")).toBeTruthy()
    await waitFor(() => expect(screen.getByText("/summary")).toBeTruthy())
  })

  it("opens the popup for an inline slash and completes in place", async () => {
    renderComposer()
    typeValue("帮我 /sum")
    await waitFor(() => expect(screen.getByText("/summary")).toBeTruthy())
    const textarea = screen.getByLabelText("消息输入框") as HTMLTextAreaElement

    fireEvent.keyDown(textarea, { key: "Tab" })

    expect(textarea.value).toBe("帮我 /summary ")
    expect(screen.queryByRole("listbox")).toBeNull()
  })

  it("executes a highlighted builtin command with Enter", async () => {
    const { onCommand } = renderComposer()
    typeValue("/com")
    await waitFor(() => expect(screen.getByText("/compact")).toBeTruthy())

    fireEvent.keyDown(screen.getByLabelText("消息输入框"), { key: "Enter" })

    expect(onCommand).toHaveBeenCalledExactlyOnceWith("compact", "")
    expect((screen.getByLabelText("消息输入框") as HTMLTextAreaElement).value).toBe("")
  })

  it("routes submissions with arguments through onCommand", async () => {
    const { onCommand } = renderComposer()
    typeValue("/skills 全部")

    fireEvent.keyDown(screen.getByLabelText("消息输入框"), { key: "Enter" })

    await waitFor(() =>
      expect(onCommand).toHaveBeenCalledExactlyOnceWith("skills", "全部"),
    )
  })

  it("expands skill invocations into an explicit directive prompt", async () => {
    const { onPromptSubmit } = renderComposer()
    typeValue("/")
    await waitFor(() => expect(screen.getByText("/summary")).toBeTruthy())

    typeValue("/summary 总结这篇论文")
    fireEvent.keyDown(screen.getByLabelText("消息输入框"), { key: "Enter" })

    await waitFor(() => expect(onPromptSubmit).toHaveBeenCalledOnce())
    const prompt = onPromptSubmit.mock.calls[0]?.[0] as string
    expect(prompt).toContain("use_skill")
    expect(prompt).toContain("summary")
    expect(prompt).toContain("总结这篇论文")
  })

  it("passes plain prompts through untouched", async () => {
    const { onPromptSubmit } = renderComposer()
    typeValue("对比两篇论文的方法")

    fireEvent.keyDown(screen.getByLabelText("消息输入框"), { key: "Enter" })

    await waitFor(() =>
      expect(onPromptSubmit).toHaveBeenCalledExactlyOnceWith("对比两篇论文的方法"),
    )
  })
})
