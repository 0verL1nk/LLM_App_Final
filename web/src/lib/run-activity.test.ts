import { describe, expect, it } from "vitest"

import { describeRunEvent, summarizeRunActivity, visibleRunEvents } from "@/lib/run-activity"
import type { AgentEvent } from "@/lib/schemas"

function event(eventType: string, payload: Record<string, unknown> = {}): AgentEvent {
  return { version: 1, eventId: "event-1", eventType, sequence: 1, timestamp: "2026-07-26T00:00:00Z", threadId: "thread", runId: "run", traceId: "trace", payload }
}

describe("run activity", () => {
  it("renders only facts supplied by the execution event", () => {
    expect(describeRunEvent(event("tool.execution.started", { trace: { receiver: "search_document" } }))).toBe("调用工具：search_document")
    expect(describeRunEvent(event("tool.execution.completed", { trace: { sender: "read_document" } }))).toBe("工具已返回：read_document")
    expect(describeRunEvent(event("run.failed", { message: "模型执行失败" }))).toBe("模型执行失败")
  })

  it("hides model-internal progress events from the user-facing activity line", () => {
    expect(visibleRunEvents([event("step.progress"), event("run.started")]).map((item) => item.eventType)).toEqual(["run.started"])
  })

  it("merges a tool lifecycle into one user-visible activity", () => {
    const started = event("tool.execution.started", { actionId: "call-1", toolName: "search_document" })
    const completed = { ...event("tool.execution.completed", { actionId: "call-1", toolName: "search_document", status: "success" }), eventId: "event-2" }
    expect(summarizeRunActivity([started, completed])).toMatchObject([
      { eventIds: ["event-1", "event-2"], label: "正在使用 search_document", status: "complete" },
    ])
  })
})
