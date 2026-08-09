import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import { describeRunEvent, summarizeRunActivity } from "@/lib/run-activity";
import type { AgentEvent } from "@/lib/schemas";

export function ResearchRunActivity({ events }: { events: AgentEvent[] }) {
  const steps = summarizeRunActivity(events);
  const activeStep = [...steps]
    .reverse()
    .find((step) => step.status === "active");
  const latestEvent = events.at(-1);
  const currentLabel = activeStep
    ? activeStep.label
    : steps.length
      ? "已完成本次资料处理"
      : latestEvent
        ? describeRunEvent(latestEvent)
        : "正在启动";
  const planEvent = [...events]
    .reverse()
    .find((event) => event.eventType === "plan.updated");
  const todos = Array.isArray(planEvent?.payload.todos)
    ? (planEvent.payload.todos as Record<string, unknown>[])
    : [];

  if (!steps.length && !todos.length) {
    return (
      <p className="mb-3 text-sm text-muted-foreground" role="status" aria-live="polite">
        {currentLabel}
      </p>
    );
  }

  return (
    <div className="mb-3" role="status" aria-live="polite">
      <ChainOfThought className="space-y-2">
        <ChainOfThoughtHeader>
          {currentLabel}
          <span className="text-xs text-muted-foreground">{steps.length} 项活动</span>
          {activeStep && (
            <span className="ml-2 inline-block size-1.5 animate-pulse rounded-full bg-current align-middle" />
          )}
        </ChainOfThoughtHeader>
        <ChainOfThoughtContent>
          {steps.map((step) => (
            <ChainOfThoughtStep
              key={step.eventIds[0]}
              label={step.label}
              status={step.status === "failed" ? "pending" : step.status === "active" ? "active" : "complete"}
            />
          ))}
          {todos.map((todo, index) => (
            <ChainOfThoughtStep
              key={String(todo.id ?? index)}
              label={String(todo.content ?? todo.title ?? todo.id ?? "未命名步骤")}
              description={String(todo.status ?? "待处理")}
              status="pending"
            />
          ))}
        </ChainOfThoughtContent>
      </ChainOfThought>
    </div>
  );
}
