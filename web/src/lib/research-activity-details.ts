import type { AgentEvent } from "@/lib/schemas";

export type ResearchTodo = {
  id: string;
  content: string;
  status: string;
  dependsOn: string[];
};

export type ToolExecution = {
  actionId: string;
  toolName: string;
  status: "active" | "complete" | "failed";
  summary: string;
  durationMs?: number;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

/** Normalize the persisted Todo contract for display without inventing states. */
export function normalizeResearchTodos(value: unknown): ResearchTodo[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item, index) => {
    const todo = asRecord(item);
    const content = String(todo?.content ?? todo?.title ?? "").trim();
    if (!content) return [];
    const dependsOn = Array.isArray(todo?.depends_on)
      ? todo.depends_on.filter((dependency): dependency is string => typeof dependency === "string")
      : [];
    return [{
      id: String(todo?.id ?? `todo-${index}`),
      content,
      status: String(todo?.status ?? "pending").trim().toLowerCase(),
      dependsOn,
    }];
  });
}

/** Return the latest Todo snapshot emitted by the real planning tool. */
export function latestPlanTodos(events: AgentEvent[]): ResearchTodo[] {
  for (const event of [...events].reverse()) {
    if (event.eventType === "plan.updated") {
      return normalizeResearchTodos(event.payload.todos);
    }
  }
  return [];
}

/** Collapse started/completed tool events into one durable user-inspectable action. */
export function summarizeToolExecutions(events: AgentEvent[]): ToolExecution[] {
  const executions = new Map<string, ToolExecution>();
  for (const event of events) {
    if (!event.eventType.startsWith("tool.execution.")) continue;
    const actionId = String(event.payload.actionId ?? event.eventId);
    const completed = event.eventType === "tool.execution.completed";
    const status = completed
      ? event.payload.status === "failed"
        ? "failed"
        : "complete"
      : "active";
    const prior = executions.get(actionId);
    executions.set(actionId, {
      actionId,
      toolName: String(event.payload.toolName ?? prior?.toolName ?? "unknown"),
      status,
      summary: String(event.payload.summary ?? prior?.summary ?? "").trim(),
      durationMs: typeof event.payload.durationMs === "number" ? event.payload.durationMs : prior?.durationMs,
    });
  }
  return [...executions.values()];
}
