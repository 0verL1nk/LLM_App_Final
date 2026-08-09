import { describe, expect, it } from "vitest"

import { createLiveRun, reduceLiveRun } from "@/lib/live-run"
import type { AgentEvent } from "@/lib/schemas"

function event(sequence: number, eventType: string, payload: Record<string, unknown> = {}): AgentEvent {
  return {
    version: 1,
    eventId: `evt-${sequence}`,
    eventType,
    sequence,
    timestamp: "2026-08-09T00:00:00Z",
    threadId: "session-1",
    runId: "run-1",
    traceId: "trace-1",
    payload,
  }
}

describe("reduceLiveRun", () => {
  it("orders a replayed stream and renders each text delta exactly once", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, event(2, "message.part.delta", { partId: "text-1", text: "世界" }))
    run = reduceLiveRun(run, event(1, "message.part.delta", { partId: "text-1", text: "你好，" }))
    run = reduceLiveRun(run, event(2, "message.part.delta", { partId: "text-1", text: "世界" }))

    expect(run.lastSequence).toBe(2)
    expect(run.parts).toEqual([{ id: "text-1", type: "markdown", text: "你好，世界" }])
  })
})
