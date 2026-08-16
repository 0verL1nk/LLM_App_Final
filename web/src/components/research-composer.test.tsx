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
    const textarea = screen.getByLabelText("消息输入框")
    fireEvent.change(textarea, { target: { value: "/" } })

    expect(screen.getByText("/skills")).toBeTruthy()
    await waitFor(() => expect(screen.getByText("/summary")).toBeTruthy())
  })

  it("executes a highlighted builtin command with Enter", async () => {
    const { onCommand } = renderComposer()
    const textarea = screen.getByLabelText("消息输入框")
    fireEvent.change(textarea, { target: { value: "/com" } })
    await waitFor(() => expect(screen.getByText("/compact")).toBeTruthy())

    fireEvent.keyDown(textarea, { key: "Enter" })

    expect(onCommand).toHaveBeenCalledExactlyOnceWith("compact", "")
    expect((textarea as HTMLTextAreaElement).value).toBe("")
  })

  it("routes submissions with arguments through onCommand", async () => {
    const { onCommand } = renderComposer()
    const textarea = screen.getByLabelText("消息输入框")
    fireEvent.change(textarea, { target: { value: "/skills 全部" } })

    fireEvent.keyDown(textarea, { key: "Enter" })

    await waitFor(() =>
      expect(onCommand).toHaveBeenCalledExactlyOnceWith("skills", "全部"),
    )
  })

  it("expands skill invocations into an explicit directive prompt", async () => {
    const { onPromptSubmit } = renderComposer()
    const textarea = screen.getByLabelText("消息输入框")
    fireEvent.change(textarea, { target: { value: "/" } })
    await waitFor(() => expect(screen.getByText("/summary")).toBeTruthy())

    fireEvent.change(textarea, { target: { value: "/summary 总结这篇论文" } })
    fireEvent.keyDown(textarea, { key: "Enter" })

    await waitFor(() => expect(onPromptSubmit).toHaveBeenCalledOnce())
    const prompt = onPromptSubmit.mock.calls[0]?.[0] as string
    expect(prompt).toContain("use_skill")
    expect(prompt).toContain("summary")
    expect(prompt).toContain("总结这篇论文")
  })

  it("passes plain prompts through untouched", async () => {
    const { onPromptSubmit } = renderComposer()
    const textarea = screen.getByLabelText("消息输入框")
    fireEvent.change(textarea, { target: { value: "对比两篇论文的方法" } })

    fireEvent.keyDown(textarea, { key: "Enter" })

    await waitFor(() =>
      expect(onPromptSubmit).toHaveBeenCalledExactlyOnceWith("对比两篇论文的方法"),
    )
  })
})
