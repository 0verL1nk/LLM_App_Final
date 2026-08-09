import { Wrench } from "lucide-react";

import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import {
  Plan,
  PlanContent,
  PlanDescription,
  PlanHeader,
  PlanTitle,
  PlanTrigger,
} from "@/components/ai-elements/plan";
import {
  Task,
  TaskContent,
  TaskItem,
  TaskTrigger,
} from "@/components/ai-elements/task";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { summarizeRunActivity } from "@/lib/run-activity";
import type { AgentEvent } from "@/lib/schemas";

export function ResearchRunActivity({ events }: { events: AgentEvent[] }) {
  const steps = summarizeRunActivity(events);
  const activeStep = [...steps]
    .reverse()
    .find((step) => step.status === "active");
  const currentLabel = activeStep
    ? activeStep.label
    : steps.length
      ? "正在整理研究结果"
      : "正在准备研究";
  const planEvent = [...events]
    .reverse()
    .find((event) => event.eventType === "plan.updated");
  const todos = Array.isArray(planEvent?.payload.todos)
    ? (planEvent.payload.todos as Record<string, unknown>[])
    : [];

  return (
    <div className="ml-11 max-w-[86%] space-y-3 py-1" role="status" aria-live="polite">
      <ChainOfThought>
        <ChainOfThoughtHeader>
          {currentLabel}
          {activeStep && (
            <span className="ml-2 inline-block size-1.5 animate-pulse rounded-full bg-current align-middle" />
          )}
        </ChainOfThoughtHeader>
        <ChainOfThoughtContent>
          {steps.map((step) => (
            <ChainOfThoughtStep
              key={step.eventIds[0]}
              icon={step.toolName ? Wrench : undefined}
              label={step.label}
              status={step.status === "failed" ? "pending" : step.status === "active" ? "active" : "complete"}
            >
              {step.toolName && (
                <Tool>
                  <ToolHeader
                    type="dynamic-tool"
                    toolName={step.toolName}
                    state={step.status === "complete" || step.status === "failed" ? "output-available" : "input-available"}
                  />
                  <ToolContent>
                    <ToolInput input={step.event.payload.arguments ?? {}} />
                    {step.status !== "active" && (
                      <ToolOutput
                        output={String(step.event.payload.summary ?? "")}
                        errorText={step.status === "failed" ? String(step.event.payload.summary ?? "处理失败") : undefined}
                      />
                    )}
                  </ToolContent>
                </Tool>
              )}
            </ChainOfThoughtStep>
          ))}
        </ChainOfThoughtContent>
      </ChainOfThought>
      {todos.length > 0 && (
        <Plan isStreaming>
          <PlanHeader>
            <div>
              <PlanTitle>研究步骤</PlanTitle>
              <PlanDescription>本次问题正在按这些步骤推进。</PlanDescription>
            </div>
            <PlanTrigger />
          </PlanHeader>
          <PlanContent>
            {todos.map((todo, index) => (
              <Task key={String(todo.id ?? index)}>
                <TaskTrigger title={String(todo.content ?? todo.title ?? todo.id ?? "未命名步骤")} />
                <TaskContent>
                  <TaskItem>{String(todo.status ?? "待处理")}</TaskItem>
                </TaskContent>
              </Task>
            ))}
          </PlanContent>
        </Plan>
      )}
    </div>
  );
}
