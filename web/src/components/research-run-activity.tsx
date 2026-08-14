import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
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
import { CheckCircle2, CircleDashed, Globe2, LoaderCircle } from "lucide-react";

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

function isWebSearch(item: LiveRunItem): boolean {
  const toolName = String(item.payload.toolName ?? item.payload.name ?? "").toLowerCase();
  return toolName.includes("web") || toolName.includes("search") || toolName.includes("browser");
}

export function ResearchRunActivity({ items = [] }: { items?: LiveRunItem[] }) {
  const toolItems = items.filter((item) => item.type === "tool_call");
  const webSearchItems = toolItems.filter(isWebSearch);
  const otherToolItems = toolItems.filter((item) => !isWebSearch(item));
  const plan = [...items].reverse().find((item) => item.type === "plan");
  const todos = Array.isArray(plan?.payload.todos) ? plan.payload.todos : [];
  const childTasks = items.filter((item) => item.type === "agent_task");
  const queuedInputs = items.filter(
    (item) => item.type === "human_request" && item.status === "in_progress",
  );

  if (!toolItems.length && !todos.length && !childTasks.length && !queuedInputs.length) {
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
      {webSearchItems.length > 0 && (
        <Task className="mb-3" defaultOpen>
          <TaskTrigger title={`联网检索 · ${webSearchItems.length} 项`} />
          <TaskContent>
            {webSearchItems.map((item) => (
              <TaskItem key={item.id} className="flex items-center gap-2">
                <Globe2 className={item.status === "in_progress" ? "size-4 animate-pulse text-primary" : "size-4"} />
                <span>{String(item.payload.summary ?? item.payload.query ?? "正在检索来源")}</span>
                <span className="ml-auto shrink-0 text-xs">{todoStatusLabel(item.status)}</span>
              </TaskItem>
            ))}
          </TaskContent>
        </Task>
      )}
      {otherToolItems.length > 0 && (
        <ChainOfThought className="space-y-2">
          <ChainOfThoughtHeader>
            正在处理资料
            <span className="text-xs text-muted-foreground">{otherToolItems.length} 项活动</span>
            {otherToolItems.some((item) => item.status === "in_progress") && (
              <span className="ml-2 inline-block size-1.5 animate-pulse rounded-full bg-current align-middle" />
            )}
          </ChainOfThoughtHeader>
          <ChainOfThoughtContent>
            {otherToolItems.map((item) => (
              <ChainOfThoughtStep
                key={item.id}
                label={String(item.payload.summary ?? item.payload.toolName ?? "工具调用")}
                status={item.status === "in_progress" ? "active" : item.status === "failed" ? "pending" : "complete"}
              />
            ))}
          </ChainOfThoughtContent>
        </ChainOfThought>
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
