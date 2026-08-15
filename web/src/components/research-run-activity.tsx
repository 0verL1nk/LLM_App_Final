import {
  Task,
  TaskContent,
  TaskItem,
  TaskTrigger,
} from "@/components/ai-elements/task";
import {
  Agent,
  AgentContent,
  AgentHeader,
  AgentInstructions,
} from "@/components/ai-elements/agent";
import {
  Queue,
  QueueItem,
  QueueItemContent,
  QueueItemIndicator,
  QueueList,
  QueueSection,
  QueueSectionContent,
  QueueSectionLabel,
  QueueSectionTrigger,
} from "@/components/ai-elements/queue";
import type { LiveRunItem } from "@/lib/live-run";
import { CheckCircle2, CircleDashed, LoaderCircle } from "lucide-react";

function todoStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    ready: "可开始",
    in_progress: "进行中",
    completed: "已完成",
    blocked: "受阻",
    failed: "失败",
    canceled: "已取消",
  };
  return labels[status] ?? (status || "待处理");
}

function todoStatusIcon(status: string) {
  if (status === "completed") return <CheckCircle2 className="size-4 text-emerald-600" aria-label="已完成" />;
  if (status === "in_progress") return <LoaderCircle className="size-4 animate-spin text-primary" aria-label="进行中" />;
  return <CircleDashed className="size-4 text-muted-foreground" aria-label="待处理" />;
}

export function ResearchRunActivity({ items = [] }: { items?: LiveRunItem[] }) {
  // Tool calls and reasoning render inside the assistant timeline in message
  // order; this block keeps only the run-level aggregates.
  const plan = [...items].reverse().find((item) => item.type === "plan");
  const todos = Array.isArray(plan?.payload.todos) ? plan.payload.todos : [];
  const childTasks = items.filter((item) => item.type === "agent_task");
  const queuedInputs = items.filter(
    (item) => item.type === "human_request" && item.status === "in_progress",
  );

  if (!todos.length && !childTasks.length && !queuedInputs.length) {
    return null;
  }

  return (
    <div className="mb-3" role="status" aria-live="polite">
      {queuedInputs.length > 0 && (
        <Queue className="mb-3">
          <QueueSection defaultOpen>
            <QueueSectionTrigger>
              <QueueSectionLabel count={queuedInputs.length} label="条追问等待处理" />
            </QueueSectionTrigger>
            <QueueSectionContent>
              <QueueList>
                {queuedInputs.map((item) => (
                    <QueueItem key={item.id}>
                      <div className="flex items-start gap-2">
                        <QueueItemIndicator />
                        <QueueItemContent>
                          {String(item.payload.text ?? "运行中追问")}
                        </QueueItemContent>
                      </div>
                    </QueueItem>
                ))}
              </QueueList>
            </QueueSectionContent>
          </QueueSection>
        </Queue>
      )}
      {todos.length > 0 && (
        <Task className="mt-3" defaultOpen={plan?.status === "in_progress"}>
          <TaskTrigger title={`执行计划 · ${todos.length} 项任务`} />
          <TaskContent>
            {todos.map((todo) => (
              <TaskItem key={todo.id} className="flex items-center gap-2">
                {todoStatusIcon(todo.status)}
                <span>{todo.content}</span>
                <span className="shrink-0 text-xs">{todoStatusLabel(todo.status)}</span>
              </TaskItem>
            ))}
          </TaskContent>
        </Task>
      )}
      {childTasks.length > 0 && (
        <Task className="mt-3" defaultOpen>
          <TaskTrigger title={`协作任务 · ${childTasks.length} 项`} />
          <TaskContent>
            {childTasks.map((item) => (
              <Agent key={item.id}>
                <AgentHeader name={String(item.payload.agent ?? item.payload.role ?? "研究子任务")} />
                <AgentContent className="space-y-2">
                  <AgentInstructions>
                    {String(item.payload.task ?? item.payload.summary ?? "研究任务")}
                  </AgentInstructions>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {todoStatusIcon(item.status)}
                    <span>{todoStatusLabel(item.status)}</span>
                  </div>
                </AgentContent>
              </Agent>
            ))}
          </TaskContent>
        </Task>
      )}
    </div>
  );
}
