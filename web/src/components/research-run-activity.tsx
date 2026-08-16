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
import { Button } from "@/components/ui/button";
import type { LiveRunItem } from "@/lib/live-run";
import { Ban, CheckCircle2, CircleDashed, CircleX, LoaderCircle } from "lucide-react";

type TaskAction = "cancel" | "retry";

export type ResearchRunControls = {
  onAction?: (taskUid: string, action: TaskAction) => void;
  capabilities?: { cancelRun?: boolean; cancelTask?: boolean; retryTask?: boolean };
  pending?: { taskUid: string; action: TaskAction } | null;
};

const DEFAULT_CAPABILITIES = { cancelRun: true, cancelTask: true, retryTask: true };

type PlanStep = { id: string; title: string; content?: string; status: string; depends_on?: string[] };

function todoStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    ready: "可开始",
    in_progress: "进行中",
    completed: "已完成",
    blocked: "受阻",
    failed: "失败",
    canceled: "已取消",
    cancelled: "已取消",
  };
  return labels[status] ?? (status || "待处理");
}

function todoStatusIcon(status: string) {
  if (status === "completed") return <CheckCircle2 className="size-4 text-emerald-600" aria-label="已完成" />;
  if (status === "in_progress") return <LoaderCircle className="size-4 animate-spin text-primary" aria-label="进行中" />;
  if (status === "failed") return <CircleX className="size-4 text-destructive" aria-label="失败" />;
  if (status === "cancelled" || status === "canceled") return <Ban className="size-4 text-muted-foreground" aria-label="已取消" />;
  return <CircleDashed className="size-4 text-muted-foreground" aria-label="待处理" />;
}

export function ResearchRunActivity({
  items = [],
  controls,
}: {
  items?: LiveRunItem[];
  controls?: ResearchRunControls;
}) {
  // Tool calls and reasoning render inside the assistant timeline in message
  // order; this block keeps only the run-level aggregates.
  const capabilities = { ...DEFAULT_CAPABILITIES, ...(controls?.capabilities ?? {}) };
  const pending = controls?.pending ?? null;
  const onAction = controls?.onAction;
  const plan = [...items].reverse().find((item) => item.type === "plan");
  const planObject = (plan?.payload?.plan ?? {}) as { steps?: PlanStep[] };
  const planSteps: PlanStep[] = Array.isArray(planObject?.steps)
    ? (planObject.steps as PlanStep[])
    : Array.isArray(plan?.payload?.steps)
      ? (plan?.payload.steps as PlanStep[])
      : [];
  const todos = Array.isArray(plan?.payload.todos) ? plan.payload.todos : planSteps;
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
                <span>{todo.content ?? todo.title}</span>
                {Array.isArray(todo.depends_on) && todo.depends_on.length > 0 && (
                  <span className="text-xs text-muted-foreground">依赖 {todo.depends_on.length} 项</span>
                )}
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
            {childTasks.map((item) => {
              const taskUid = String(item.taskId ?? item.id);
              const cancelPending = pending?.taskUid === taskUid && pending.action === "cancel";
              const retryPending = pending?.taskUid === taskUid && pending.action === "retry";
              const retryable = item.status === "failed" || item.status === "cancelled" || item.status === "canceled";
              return (
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
                    {(retryable || item.status === "in_progress") && (
                      <div className="flex items-center gap-2">
                        {cancelPending && <span className="text-xs">取消中…</span>}
                        {retryPending && <span className="text-xs">重试中…</span>}
                        {item.status === "in_progress" && capabilities.cancelTask && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            aria-label={`取消任务 ${item.id}`}
                            disabled={cancelPending || retryPending}
                            onClick={() => onAction?.(taskUid, "cancel")}
                          >
                            取消任务
                          </Button>
                        )}
                        {retryable && capabilities.retryTask && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            aria-label={`重试任务 ${item.id}`}
                            disabled={cancelPending || retryPending}
                            onClick={() => onAction?.(taskUid, "retry")}
                          >
                            重试任务
                          </Button>
                        )}
                      </div>
                    )}
                  </AgentContent>
                </Agent>
              );
            })}
          </TaskContent>
        </Task>
      )}
    </div>
  );
}
