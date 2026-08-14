import { describe, expect, it } from "vitest";

import { latestPlanTodos, summarizeToolExecutions } from "@/lib/research-activity-details";
import type { AgentEvent } from "@/lib/schemas";

function event(eventType: string, payload: Record<string, unknown>, sequence: number): AgentEvent {
  return {
    version: 1,
    eventId: `event-${sequence}`,
    eventType,
    sequence,
    timestamp: "2026-08-09T00:00:00Z",
    threadId: "thread-1",
    runId: "run-1",
    traceId: "trace-1",
    payload,
  };
}

describe("research activity details", () => {
  it("uses the latest todo snapshot emitted by the planning tool", () => {
    const todos = latestPlanTodos([
      event("plan.updated", { todos: [{ id: "old", content: "旧任务", status: "completed" }] }, 1),
      event("plan.updated", { todos: [{ id: "new", content: "检索证据", status: "in_progress", depends_on: ["source"] }] }, 2),
    ]);

    expect(todos).toEqual([{ id: "new", content: "检索证据", status: "in_progress", dependsOn: ["source"] }]);
  });

  it("merges a real tool lifecycle instead of showing duplicate activities", () => {
    const tools = summarizeToolExecutions([
      event("tool.execution.started", { actionId: "search-1", toolName: "search_document" }, 1),
      event("tool.execution.completed", { actionId: "search-1", toolName: "search_document", summary: "找到 6 条资料", status: "success", durationMs: 80 }, 2),
    ]);

    expect(tools).toEqual([{ actionId: "search-1", toolName: "search_document", status: "complete", summary: "找到 6 条资料", durationMs: 80 }]);
  });
});
