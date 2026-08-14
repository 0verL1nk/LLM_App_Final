import type { AgentEvent } from "@/lib/schemas"

export interface RunActivityStep {
  event: AgentEvent
  eventIds: string[]
  label: string
  status: "active" | "complete" | "failed"
  toolName?: string
}

function traceValue(event: AgentEvent, key: string): string {
  const trace = event.payload.trace
  if (!trace || typeof trace !== "object" || Array.isArray(trace)) return ""
  const value = (trace as Record<string, unknown>)[key]
  return typeof value === "string" ? value.trim() : ""
}

export function describeRunEvent(event: AgentEvent): string {
  if (event.eventType === "run.created") return "请求已排队"
  if (event.eventType === "run.started") return "任务已开始"
  if (event.eventType === "run.completed") return "任务已完成"
  if (event.eventType === "plan.updated") return "任务计划已更新"
  if (event.eventType === "run.failed") return String(event.payload.message ?? "任务失败")
  if (event.eventType === "agent.spawned") return "已创建子任务"
  if (event.eventType === "agent.completed") return "子任务已返回"
  if (event.eventType === "tool.execution.started") return `调用工具：${String(event.payload.toolName ?? traceValue(event, "receiver") ?? "未知工具")}`
  if (event.eventType === "tool.execution.completed") return `工具已返回：${String(event.payload.toolName ?? traceValue(event, "sender") ?? "未知工具")}`
  return "已记录运行事件"
}

export function visibleRunEvents(events: AgentEvent[]): AgentEvent[] {
  return events.filter((event) => ["run.failed", "plan.updated", "agent.spawned", "agent.completed", "tool.execution.started", "tool.execution.completed"].includes(event.eventType))
}

/**
 * Collapse lifecycle pairs by their runtime action id.  This uses the durable
 * tool/agent-task contract rather than inferring stages from display strings.
 */
export function summarizeRunActivity(events: AgentEvent[]): RunActivityStep[] {
  const steps: RunActivityStep[] = []
  const byActionId = new Map<string, RunActivityStep>()
  for (const event of visibleRunEvents(events)) {
    if (event.eventType === "plan.updated") continue
    if (event.eventType === "run.failed") {
      steps.push({ event, eventIds: [event.eventId], label: describeRunEvent(event), status: "failed" })
      continue
    }
    const actionId = String(event.payload.actionId ?? event.eventId)
    const lifecycleStart = event.eventType === "tool.execution.started" || event.eventType === "agent.spawned"
    const existing = byActionId.get(actionId)
    if (lifecycleStart && !existing) {
      const label = event.eventType === "agent.spawned" ? `正在进行协作任务：${String(event.payload.agent ?? "研究助手")}` : `正在使用 ${String(event.payload.toolName ?? "工具")}`
      const step = { event, eventIds: [event.eventId], label, status: "active" as const, toolName: event.eventType.startsWith("tool.") ? String(event.payload.toolName ?? "unknown") : undefined }
      byActionId.set(actionId, step)
      steps.push(step)
      continue
    }
    if (existing) {
      existing.event = event
      existing.eventIds.push(event.eventId)
      existing.status = event.payload.status === "failed" ? "failed" : "complete"
      continue
    }
    const label = event.eventType === "agent.completed" ? `协作任务已返回：${String(event.payload.agent ?? "研究助手")}` : `已使用 ${String(event.payload.toolName ?? "工具")}`
    steps.push({ event, eventIds: [event.eventId], label, status: event.payload.status === "failed" ? "failed" : "complete", toolName: event.eventType.startsWith("tool.") ? String(event.payload.toolName ?? "unknown") : undefined })
  }
  return steps
}
