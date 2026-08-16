// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ResearchRunActivity } from "@/components/research-run-activity"
import type { LiveRunItem } from "@/lib/live-run"

afterEach(cleanup)

function childItem(id: string, taskId: string, status: string, agent = "证据研究"): LiveRunItem {
  return {
    id,
    type: "agent_task",
    status,
    taskId,
    payload: { agent, task: `任务 ${taskId}`, summary: "已加入任务队列" },
    sequence: 0,
    order: 0,
    updatedAt: "2026-08-15T00:00:00Z",
  }
}

describe("ResearchRunActivity", () => {
  it("renders two same-role children as independent cards with their own status", () => {
    render(
      <ResearchRunActivity
        items={[
          childItem("item_agent_task_task-a", "task-a", "in_progress"),
          childItem("item_agent_task_task-b", "task-b", "completed"),
        ]}
      />,
    )

    expect(screen.getByText("任务 task-a")).toBeTruthy()
    expect(screen.getByText("任务 task-b")).toBeTruthy()
    expect(screen.getAllByText("证据研究")).toHaveLength(2)
    expect(screen.getByText("进行中")).toBeTruthy()
    expect(screen.getByText("已完成")).toBeTruthy()
  })

  it("shows cancel only for in-progress tasks and retry only after terminal failure", () => {
    const onAction = vi.fn()
    render(
      <ResearchRunActivity
        items={[
          childItem("item_agent_task_task-a", "task-a", "in_progress"),
          childItem("item_agent_task_task-b", "task-b", "failed"),
          childItem("item_agent_task_task-c", "task-c", "cancelled"),
          childItem("item_agent_task_task-d", "task-d", "completed"),
        ]}
        controls={{ onAction }}
      />,
    )

    expect(screen.getAllByRole("button", { name: /^取消任务/ })).toHaveLength(1)
    // failed and cancelled children are retryable; the completed one is not.
    expect(screen.getAllByRole("button", { name: /^重试任务/ })).toHaveLength(2)

    fireEvent.click(screen.getByRole("button", { name: "取消任务 item_agent_task_task-a" }))
    expect(onAction).toHaveBeenCalledWith("task-a", "cancel")
    fireEvent.click(screen.getByRole("button", { name: "重试任务 item_agent_task_task-b" }))
    expect(onAction).toHaveBeenCalledWith("task-b", "retry")
  })

  it("hides task controls when the server capability is absent", () => {
    render(
      <ResearchRunActivity
        items={[childItem("item_agent_task_task-a", "task-a", "failed")]}
        controls={{ capabilities: { cancelRun: true, cancelTask: false, retryTask: false } }}
      />,
    )

    expect(screen.queryByRole("button", { name: /取消任务/ })).toBeNull()
    expect(screen.queryByRole("button", { name: /重试任务/ })).toBeNull()
    expect(screen.getByText("失败")).toBeTruthy()
  })

  it("shows pending copy while a task mutation is in flight", () => {
    render(
      <ResearchRunActivity
        items={[childItem("item_agent_task_task-a", "task-a", "failed")]}
        controls={{ pending: { taskUid: "task-a", action: "retry" } }}
      />,
    )

    expect(screen.getByText("重试中…")).toBeTruthy()
    expect(screen.getByRole("button", { name: /重试任务/ }).hasAttribute("disabled")).toBe(true)
  })

  it("feeds plan steps from the typed V2 plan payload", () => {
    const planItem: LiveRunItem = {
      id: "item_plan_update-1",
      type: "plan",
      status: "in_progress",
      taskId: null,
      payload: {
        toolName: "update_plan",
        summary: "更新计划",
        plan: {
          goal: "比较两篇论文的方法",
          steps: [
            { id: "s1", title: "检索文献", status: "completed", depends_on: [], lane: "main" },
            { id: "s2", title: "交叉核验", status: "in_progress", depends_on: ["s1"], lane: "verify" },
          ],
        },
      },
      sequence: 1,
      order: 1,
      updatedAt: "2026-08-15T00:00:00Z",
    }
    render(<ResearchRunActivity items={[planItem]} />)

    expect(screen.getByText("执行计划 · 2 项任务")).toBeTruthy()
    expect(screen.getByText("检索文献")).toBeTruthy()
    expect(screen.getByText("交叉核验")).toBeTruthy()
    expect(screen.getByText("依赖 1 项")).toBeTruthy()
  })
})
