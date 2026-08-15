// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { useMemo } from "react"
import { afterEach, describe, expect, it } from "vitest"

import { ResearchRunActivity } from "@/components/research-run-activity"
import {
  createLiveRun,
  hydrateLiveRun,
  liveAnswer,
  liveMessageParts,
  liveRunItems,
  reduceLiveRun,
} from "@/lib/live-run"
import type { AgentEvent } from "@/lib/schemas"
import type { RunItemsResponse } from "@/lib/run-items"

afterEach(cleanup)

function v2Event(
  sequence: number,
  eventType: string,
  item?: AgentEvent["item"],
): AgentEvent {
  return {
    version: 2,
    eventId: `evt-${sequence}`,
    eventType,
    sequence,
    timestamp: `2026-08-15T00:00:${String(sequence).padStart(2, "0")}Z`,
    threadId: "session-1",
    runId: "run-1",
    traceId: "trace-1",
    payload: {},
    item,
  }
}

function childEvent(sequence: number, eventType: string, status: string, taskId: string): AgentEvent {
  return v2Event(sequence, eventType, {
    id: `item_agent_task_${taskId}`,
    type: "agent_task",
    status,
    taskId,
    payload: { agent: "证据研究", task: `任务 ${taskId}`, summary: "已加入任务队列" },
  })
}

function deltaEvent(sequence: number, delta: string): AgentEvent {
  return v2Event(sequence, "item.delta", {
    id: "item_assistant_message_text-0",
    type: "assistant_message",
    status: "in_progress",
    taskId: null,
    payload: { partId: "text-0", delta },
  })
}

/**
 * Harness that mirrors the page wiring: optional snapshot hydration, then a
 * list of stream batches (one per connect) applied through the reducer in
 * arrival order.
 */
function LiveRunStreamView({
  snapshot,
  batches,
}: {
  snapshot?: RunItemsResponse
  batches: AgentEvent[][]
}) {
  const run = useMemo(() => {
    let state = hydrateLiveRun(createLiveRun("run-1"), snapshot ?? { items: [], lastSequence: 0 })
    for (const batch of batches) {
      for (const event of batch) state = reduceLiveRun(state, event)
    }
    return state
  }, [snapshot, batches])
  const items = liveRunItems(run)
  return (
    <div>
      <p data-testid="run-status">{run.status}</p>
      <p data-testid="answer">{liveAnswer(liveMessageParts(items))}</p>
      <ResearchRunActivity items={items} />
    </div>
  )
}

describe("live run stream through React", () => {
  it("renders the answer exactly once when a reconnect replays the full window", () => {
    const first = [deltaEvent(1, "根据 "), deltaEvent(2, "两篇论文")]
    const { rerender } = render(<LiveRunStreamView batches={[first]} />)
    expect(screen.getByTestId("answer").textContent).toBe("根据 两篇论文")

    // Second connect replays sequences 1-2 before continuing with 3.
    rerender(<LiveRunStreamView batches={[first, [...first, deltaEvent(3, "的实验")]]} />)
    expect(screen.getByTestId("answer").textContent).toBe("根据 两篇论文的实验")
  })

  it("assembles ordered output when events arrive late", () => {
    const { rerender } = render(
      <LiveRunStreamView batches={[[deltaEvent(3, "结论"), deltaEvent(1, "首先，")]]} />,
    )
    // Sequence 1 applies; the missing sequence 2 stalls the rest in order.
    expect(screen.getByTestId("answer").textContent).toBe("首先，")

    rerender(
      <LiveRunStreamView batches={[[deltaEvent(3, "结论"), deltaEvent(1, "首先，")], [deltaEvent(2, "推导")]]} />,
    )
    expect(screen.getByTestId("answer").textContent).toBe("首先，推导结论")
  })

  it("hydrates a snapshot and continues from its cursor without duplicate text", () => {
    const snapshot: RunItemsResponse = {
      items: [
        {
          id: "item_assistant_message_text-0",
          taskId: null,
          type: "assistant_message",
          status: "in_progress",
          payload: { partId: "text-0", text: "合并后的段落。" },
          sequence: 4,
          createdAt: "2026-08-15T00:00:00Z",
          updatedAt: "2026-08-15T00:00:04Z",
        },
      ],
      lastSequence: 4,
    }
    const { rerender } = render(
      <LiveRunStreamView snapshot={snapshot} batches={[[deltaEvent(5, "续写")]]} />,
    )
    expect(screen.getByTestId("answer").textContent).toBe("合并后的段落。续写")

    // A reconnect that wrongly replays the hydrated window stays idempotent.
    rerender(
      <LiveRunStreamView snapshot={snapshot} batches={[[deltaEvent(3, "旧增量"), deltaEvent(5, "续写")]]} />,
    )
    expect(screen.getByTestId("answer").textContent).toBe("合并后的段落。续写")
  })

  it("renders two same-role children and a cancelled task with retry state", () => {
    const batches = [[
      childEvent(1, "item.created", "in_progress", "task-a"),
      childEvent(2, "item.created", "in_progress", "task-b"),
      childEvent(3, "item.completed", "completed", "task-a"),
      childEvent(4, "item.cancelled", "cancelled", "task-b"),
      v2Event(5, "run.completed"),
    ]]
    render(<LiveRunStreamView batches={batches} />)

    expect(screen.getByTestId("run-status").textContent).toBe("completed")
    expect(screen.getByText("任务 task-a")).toBeTruthy()
    expect(screen.getByText("任务 task-b")).toBeTruthy()
    expect(screen.getByText("已完成")).toBeTruthy()
    expect(screen.getByText("已取消")).toBeTruthy()
    expect(screen.getByRole("button", { name: "重试任务 item_agent_task_task-b" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: /取消任务/ })).toBeNull()
  })
})
