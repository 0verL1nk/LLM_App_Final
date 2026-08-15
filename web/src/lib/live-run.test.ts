import { describe, expect, it } from "vitest"

import { buildLiveTimeline } from "@/components/assistant-run-timeline"
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

function reasoningItemEvent(sequence: number, partId: string, delta: string): AgentEvent {
  return {
    ...event(sequence, "item.delta"),
    version: 2,
    item: {
      id: `item-reasoning-${partId}`,
      type: "reasoning_summary",
      status: "in_progress",
      payload: { partId, delta },
    },
  }
}

function toolEvent(sequence: number, status: string): AgentEvent {
  return {
    ...event(sequence, "item.updated"),
    version: 2,
    item: {
      id: "item-tool-1",
      type: "tool_call",
      status,
      payload: { toolName: "search_document", summary: "检索项目资料" },
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

  it("keeps exactly one arrival marker per streamed part", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, textItemEvent(1, "第一"))
    run = reduceLiveRun(run, textItemEvent(2, "段"))
    run = reduceLiveRun(run, textItemEvent(3, "更多"))

    expect(run.events).toHaveLength(1)
    expect(run.events[0]?.sequence).toBe(1)
  })

  it("interleaves reasoning segments and tool calls in arrival order", () => {
    let run = createLiveRun()
    run = reduceLiveRun(run, textItemEvent(1, "先定位", "reasoning_summary"))
    run = reduceLiveRun(run, toolEvent(2, "in_progress"))
    run = reduceLiveRun(run, toolEvent(3, "completed"))
    run = reduceLiveRun(run, reasoningItemEvent(4, "reasoning-1", "再综合"))

    const steps = buildLiveTimeline(run)

    expect(steps.map((step) => step.kind)).toEqual(["reasoning", "tool", "reasoning"])
    expect(steps[0]).toMatchObject({ id: "reasoning:reasoning-0", text: "先定位" })
    expect(steps[1]).toMatchObject({ kind: "tool", label: "检索项目资料", status: "completed" })
    expect(steps[2]).toMatchObject({ id: "reasoning:reasoning-1", text: "再综合" })
  })
})
