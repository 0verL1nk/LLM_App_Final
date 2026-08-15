import { describe, expect, it } from "vitest"

import {
  RUN_SERVER_CAPABILITIES,
  agentTaskDetailSchema,
  canCancelTask,
  canRetryTask,
  isTaskRetrying,
  parseItemPayload,
  planItemPayloadSchema,
  runItemsResponseSchema,
  toolCallPayloadSchema,
} from "@/lib/run-items"

describe("run item contracts", () => {
  it("parses the items snapshot response with its replay cursor", () => {
    const snapshot = runItemsResponseSchema.parse({
      items: [
        {
          id: "item_agent_task_task-a",
          taskId: "task-a",
          type: "agent_task",
          status: "completed",
          payload: { agent: "证据研究", task: "核验结论", summary: "完成" },
          sequence: 7,
          createdAt: "2026-08-15T00:00:00Z",
          updatedAt: "2026-08-15T00:00:07Z",
        },
      ],
      lastSequence: 9,
    })
    expect(snapshot.items[0].taskId).toBe("task-a")
    expect(snapshot.lastSequence).toBe(9)
  })

  it("defaults missing snapshot items to an empty hydration", () => {
    const snapshot = runItemsResponseSchema.parse({ lastSequence: 4 })
    expect(snapshot.items).toEqual([])
    expect(snapshot.lastSequence).toBe(4)
  })

  it("extracts typed payloads and degrades malformed payloads to defaults", () => {
    const plan = parseItemPayload(planItemPayloadSchema, {
      plan: { goal: "比较方法", steps: [{ id: "s1", title: "检索", depends_on: ["s0"] }] },
    })
    expect(plan.plan?.steps[0]).toMatchObject({ id: "s1", title: "检索", depends_on: ["s0"], lane: "main" })

    const broken = parseItemPayload(toolCallPayloadSchema, { summary: 42 })
    expect(broken.summary == null).toBe(true)
    expect(parseItemPayload(planItemPayloadSchema, null).plan).toBeUndefined()
  })

  it("parses the durable task detail with attempts and terminal gating", () => {
    const task = agentTaskDetailSchema.parse({
      task_uid: "task-a",
      run_uid: "run-1",
      status: "failed",
      agent_role: "证据研究",
      input: { objective: "核验" },
      result: {},
      created_at: "2026-08-15T00:00:00Z",
      updated_at: "2026-08-15T00:00:09Z",
      attempts: [
        {
          attempt_uid: "attempt-1",
          task_uid: "task-a",
          worker_id: "worker-1",
          attempt_number: 1,
          status: "failed",
          lease_expires_at: "2026-08-15T00:00:05Z",
          heartbeat_at: "2026-08-15T00:00:04Z",
          error_category: "model_error",
        },
      ],
    })
    expect(task.attempts[0].error_category).toBe("model_error")
    expect(canCancelTask(task.status)).toBe(false)
    expect(canRetryTask(task.status)).toBe(true)
    expect(isTaskRetrying(task)).toBe(false)

    const retrying = { ...task, status: "running", attempts: [...task.attempts, { ...task.attempts[0], attempt_uid: "attempt-2", attempt_number: 2, status: "running", error_category: "" }] }
    expect(isTaskRetrying(retrying)).toBe(true)
    expect(canCancelTask(retrying.status)).toBe(true)
  })

  it("gates task mutations behind the advertised server capabilities", () => {
    expect(RUN_SERVER_CAPABILITIES.cancelTask).toBe(true)
    expect(canCancelTask("queued")).toBe(true)
    expect(canCancelTask("expired")).toBe(false)
    expect(canRetryTask("completed")).toBe(false)
    expect(canRetryTask("expired")).toBe(true)
  })
})
