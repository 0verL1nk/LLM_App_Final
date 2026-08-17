import { describe, expect, it } from "vitest"

import { assistantParts, createLiveRun, reduceLiveRun } from "@/lib/live-run"
import { turnResultSchema } from "@/lib/schemas"
import type { AgentEvent, Message } from "@/lib/schemas"

function itemEvent(item: NonNullable<AgentEvent["item"]>, sequence: number): AgentEvent {
  return {
    version: 2,
    eventId: `evt_${sequence}`,
    eventType: "item.delta",
    sequence,
    timestamp: "",
    threadId: "",
    runId: "",
    traceId: "",
    payload: {},
    item,
  }
}

describe("turn completion keeps the inline part order", () => {
  it("parses response_parts from the run result so the completion message can render inline", () => {
    const parsed = turnResultSchema.parse({
      answer: "正文",
      response_parts: [
        { id: "text-0", type: "markdown", text: "正文前半" },
        { id: "surface-0", type: "a2ui", surfaceId: "research-map-1" },
        { id: "text-1", type: "markdown", text: "正文后半" },
      ],
    })
    expect(parsed.response_parts?.map((part) => part.id)).toEqual(["text-0", "surface-0", "text-1"])
  })

  it("renders persisted interleaved parts in order instead of appending surfaces after the text", () => {
    const message: Message = {
      role: "assistant",
      content: "全文",
      parts: [
        { id: "text-0", type: "markdown", text: "正文前半" },
        { id: "surface-0", type: "a2ui", surfaceId: "research-map-1" },
        { id: "text-1", type: "markdown", text: "正文后半" },
      ],
    }
    expect(assistantParts(message).map((part) => part.id)).toEqual(["text-0", "surface-0", "text-1"])
  })

  it("keeps the legacy text-then-surface fallback for messages stored before parts existed", () => {
    const message: Message = {
      role: "assistant",
      content: "全文",
      a2ui: [{ surfaceId: "research-map-1" }],
    }
    expect(assistantParts(message).map((part) => part.id)).toEqual(["text-0", "surface-0"])
  })
})

describe("live presentation failure", () => {
  it("drops the placeholder part when the fragment fails so no skeleton lingers", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, itemEvent({ id: "item_presentation_surface-0", type: "presentation", status: "in_progress", payload: { partId: "surface-0", presentation: "a2ui" } }, 1))
    run = reduceLiveRun(run, itemEvent({ id: "item_presentation_surface-0", type: "presentation", status: "failed", payload: { partId: "surface-0", message: "UI fragment ended before its closing tag" } }, 2))
    expect(run.parts.find((part) => part.id === "surface-0")).toBeUndefined()
  })
})
