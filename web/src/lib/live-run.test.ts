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

function itemEvent(sequence: number, status: string): AgentEvent {
  return {
    ...event(sequence, status === "completed" ? "item.completed" : "item.created"),
    version: 2,
    item: {
      id: "item-child-1",
      type: "agent_task",
      status,
      taskId: "task-child-1",
      payload: { task: "核验实验结论" },
    },
  }
}

function textItemEvent(sequence: number, delta: string, type: "assistant_message" | "reasoning_summary" = "assistant_message"): AgentEvent {
  return {
    ...event(sequence, "item.delta"),
    version: 2,
    item: {
      id: `item-${type}-text-0`,
      type,
      status: "in_progress",
      payload: { partId: type === "reasoning_summary" ? "reasoning-0" : "text-0", delta },
    },
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

  it("keeps a reasoning stream separate from answer markdown", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, event(1, "message.part.insert", { partId: "reasoning-0", type: "reasoning" }))
    run = reduceLiveRun(run, event(2, "message.part.delta", { partId: "reasoning-0", text: "先核验资料" }))
    run = reduceLiveRun(run, event(3, "message.part.delta", { partId: "text-0", text: "结论" }))

    expect(run.parts).toEqual([
      { id: "reasoning-0", type: "reasoning", text: "先核验资料" },
      { id: "text-0", type: "markdown", text: "结论" },
    ])
  })

  it("updates one durable child-task card from its item lifecycle", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, itemEvent(1, "in_progress"))
    run = reduceLiveRun(run, itemEvent(2, "completed"))

    expect(run.items).toEqual({
      "item-child-1": {
        id: "item-child-1",
        type: "agent_task",
        status: "completed",
        taskId: "task-child-1",
        payload: { task: "核验实验结论" },
      },
    })
  })

  it("renders V2 message and reasoning deltas without a V1 timeline event", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, textItemEvent(1, "先核验"))
    run = reduceLiveRun(run, textItemEvent(2, "证据", "reasoning_summary"))
    run = reduceLiveRun(run, textItemEvent(3, "结论"))

    expect(run.parts).toEqual([
      { id: "text-0", type: "markdown", text: "先核验结论" },
      { id: "reasoning-0", type: "reasoning", text: "证据" },
    ])
  })
})
