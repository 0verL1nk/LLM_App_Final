import { z } from "zod"

/**
 * V2 Run-item contracts shared with the server (agent/domain/run_item.py).
 *
 * The server validates these shapes before persistence; the web parses them
 * tolerantly so a newer server can add fields or item kinds without killing an
 * in-flight stream. Unknown item kinds are tracked but never rendered.
 */

export const RUN_ITEM_TYPES = [
  "assistant_message",
  "reasoning_summary",
  "plan",
  "tool_call",
  "agent_task",
  "human_request",
  "presentation",
  "failure",
] as const

export type RunItemType = (typeof RUN_ITEM_TYPES)[number]

export const RUN_ITEM_STATUSES = ["in_progress", "completed", "failed", "cancelled"] as const

export type RunItemStatus = (typeof RUN_ITEM_STATUSES)[number]

export const RUN_ITEM_EVENT_TYPES = [
  "item.created",
  "item.delta",
  "item.completed",
  "item.failed",
  "item.cancelled",
] as const

export type RunItemEventType = (typeof RUN_ITEM_EVENT_TYPES)[number]

const TERMINAL_ITEM_STATUSES: ReadonlySet<string> = new Set(["completed", "failed", "cancelled"])

export function isTerminalItemStatus(status: string): boolean {
  return TERMINAL_ITEM_STATUSES.has(status)
}

export function isKnownItemType(type: string): type is RunItemType {
  return (RUN_ITEM_TYPES as readonly string[]).includes(type)
}

/** Envelope carried by every V2 item event; item identity is the item id. */
export const runItemEnvelopeSchema = z.object({
  id: z.string().min(1),
  type: z.string(),
  status: z.string(),
  taskId: z.string().nullable().default(null),
  payload: z.record(z.string(), z.unknown()).default({}),
})

export type RunItemEnvelope = z.infer<typeof runItemEnvelopeSchema>

const textPartPayloadSchema = z.looseObject({
  partId: z.string().default(""),
  text: z.string().nullish(),
  delta: z.string().nullish(),
})

export const assistantMessagePayloadSchema = textPartPayloadSchema
export const reasoningSummaryPayloadSchema = textPartPayloadSchema

export const planStepPayloadSchema = z.looseObject({
  id: z.string().default(""),
  title: z.string().default(""),
  status: z.string().default("pending"),
  depends_on: z.array(z.string()).default([]),
  lane: z.string().default("main"),
  task_uid: z.string().nullish(),
})

export const planSnapshotPayloadSchema = z.looseObject({
  goal: z.string().nullish(),
  revision: z.number().int().nonnegative().nullish(),
  steps: z.array(planStepPayloadSchema).default([]),
})

export const planItemPayloadSchema = z.looseObject({
  summary: z.string().nullish(),
  toolName: z.string().nullish(),
  durationMs: z.number().nonnegative().nullish(),
  plan: planSnapshotPayloadSchema.nullish(),
})

export const toolCallPayloadSchema = z.looseObject({
  summary: z.string().nullish(),
  toolName: z.string().nullish(),
  durationMs: z.number().nonnegative().nullish(),
})

export const agentTaskPayloadSchema = z.looseObject({
  agent: z.string().nullish(),
  task: z.string().nullish(),
  summary: z.string().nullish(),
})

export const humanRequestPayloadSchema = z.looseObject({
  inputId: z.string().nullish(),
  text: z.string().nullish(),
  state: z.string().nullish(),
})

export const presentationPayloadSchema = z.looseObject({
  partId: z.string().default(""),
  presentation: z.string().nullish(),
  envelope: z.record(z.string(), z.unknown()).nullish(),
  envelopes: z.array(z.record(z.string(), z.unknown())).nullish(),
  surface: z.record(z.string(), z.unknown()).nullish(),
  surfaceId: z.string().nullish(),
  title: z.string().nullish(),
  message: z.string().nullish(),
})

export const failurePayloadSchema = z.looseObject({
  message: z.string().default(""),
  category: z.string().nullish(),
})

export type AssistantMessagePayload = z.infer<typeof assistantMessagePayloadSchema>
export type ReasoningSummaryPayload = z.infer<typeof reasoningSummaryPayloadSchema>
export type PlanStepPayload = z.infer<typeof planStepPayloadSchema>
export type PlanSnapshotPayload = z.infer<typeof planSnapshotPayloadSchema>
export type PlanItemPayload = z.infer<typeof planItemPayloadSchema>
export type ToolCallPayload = z.infer<typeof toolCallPayloadSchema>
export type AgentTaskPayload = z.infer<typeof agentTaskPayloadSchema>
export type HumanRequestPayload = z.infer<typeof humanRequestPayloadSchema>
export type PresentationPayload = z.infer<typeof presentationPayloadSchema>
export type FailurePayload = z.infer<typeof failurePayloadSchema>

const ITEM_PAYLOAD_SCHEMAS: Record<RunItemType, z.ZodType> = {
  assistant_message: assistantMessagePayloadSchema,
  reasoning_summary: reasoningSummaryPayloadSchema,
  plan: planItemPayloadSchema,
  tool_call: toolCallPayloadSchema,
  agent_task: agentTaskPayloadSchema,
  human_request: humanRequestPayloadSchema,
  presentation: presentationPayloadSchema,
  failure: failurePayloadSchema,
}

/**
 * Extract a typed payload without ever throwing: malformed or partial data
 * degrades to schema defaults instead of breaking rendering.
 */
export function parseItemPayload<T extends z.ZodType>(schema: T, payload: unknown): z.output<T> {
  const parsed = schema.safeParse(payload ?? {})
  return parsed.success ? parsed.data : (schema.parse({}) as z.output<T>)
}

export function itemPayloadSchema(type: string): z.ZodType | undefined {
  return isKnownItemType(type) ? ITEM_PAYLOAD_SCHEMAS[type] : undefined
}

/** GET /runs/{run_uid}/items snapshot row (server keeps merged payload text). */
export const runItemSnapshotSchema = z.object({
  id: z.string().min(1),
  taskId: z.string().nullable().default(null),
  type: z.string(),
  status: z.string(),
  payload: z.record(z.string(), z.unknown()).default({}),
  sequence: z.number().int().nonnegative(),
  createdAt: z.string().default(""),
  updatedAt: z.string().default(""),
})

export const runItemsResponseSchema = z.object({
  items: z.array(runItemSnapshotSchema).default([]),
  lastSequence: z.number().int().nonnegative(),
})

export type RunItemSnapshot = z.infer<typeof runItemSnapshotSchema>
export type RunItemsResponse = z.infer<typeof runItemsResponseSchema>

/** Durable AgentTask attempt projection from GET /tasks/{task_uid}. */
export const agentTaskAttemptSchema = z.object({
  attempt_uid: z.string(),
  task_uid: z.string(),
  worker_id: z.string().default(""),
  attempt_number: z.number().int().positive(),
  status: z.string(),
  lease_expires_at: z.string().default(""),
  heartbeat_at: z.string().default(""),
  started_at: z.string().nullable().default(null),
  finished_at: z.string().nullable().default(null),
  error_category: z.string().default(""),
  error_message: z.string().default(""),
})

export const agentTaskDetailSchema = z.object({
  task_uid: z.string(),
  run_uid: z.string(),
  parent_task_uid: z.string().nullable().default(null),
  kind: z.string().default(""),
  agent_role: z.string().default(""),
  status: z.string(),
  continuation_epoch: z.number().int().default(0),
  input: z.record(z.string(), z.unknown()).default({}),
  result: z.record(z.string(), z.unknown()).default({}),
  error_message: z.string().default(""),
  cancel_requested_at: z.string().nullable().default(null),
  created_at: z.string().default(""),
  started_at: z.string().nullable().default(null),
  finished_at: z.string().nullable().default(null),
  updated_at: z.string().default(""),
  attempts: z.array(agentTaskAttemptSchema).default([]),
})

export type AgentTaskAttempt = z.infer<typeof agentTaskAttemptSchema>
export type AgentTaskDetail = z.infer<typeof agentTaskDetailSchema>

/**
 * Mutations this server generation exposes. Controls render only when both the
 * capability and the current task state allow them.
 */
export const RUN_SERVER_CAPABILITIES: RunServerCapabilities = {
  cancelRun: true,
  cancelTask: true,
  retryTask: true,
}

export type RunServerCapabilities = {
  cancelRun: boolean
  cancelTask: boolean
  retryTask: boolean
}

const TERMINAL_TASK_STATUSES: ReadonlySet<string> = new Set(["completed", "failed", "cancelled", "expired"])

export function isTerminalTaskStatus(status: string): boolean {
  return TERMINAL_TASK_STATUSES.has(status)
}

export function canCancelTask(status: string): boolean {
  return !TERMINAL_TASK_STATUSES.has(status)
}

export function canRetryTask(status: string): boolean {
  return status === "failed" || status === "cancelled" || status === "expired"
}

/** A re-queued attempt after an earlier failure is a retry, judged from attempts. */
export function isTaskRetrying(task: AgentTaskDetail | undefined): boolean {
  if (!task || TERMINAL_TASK_STATUSES.has(task.status)) return false
  return task.attempts.length > 1 && task.attempts.slice(0, -1).some((attempt) => attempt.status === "failed")
}

const TASK_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  leased: "已认领",
  running: "进行中",
  waiting_children: "等待子任务",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  expired: "已过期",
}

export function taskStatusLabel(status: string): string {
  return TASK_STATUS_LABELS[status] ?? (status || "未知")
}

const ITEM_STATUS_LABELS: Record<string, string> = {
  in_progress: "进行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
}

export function itemStatusLabel(status: string): string {
  return ITEM_STATUS_LABELS[status] ?? (status || "进行中")
}

const PLAN_STEP_STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  in_progress: "进行中",
  completed: "已完成",
  blocked: "受阻",
  failed: "失败",
}

export function planStepStatusLabel(status: string): string {
  return PLAN_STEP_STATUS_LABELS[status] ?? (status || "待处理")
}
