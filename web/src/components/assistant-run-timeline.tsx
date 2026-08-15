import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import { Tool, ToolHeader } from "@/components/ai-elements/tool";
import type { LiveRun, RenderedMessagePart } from "@/lib/live-run";
import { cn } from "@/lib/utils";

export type AssistantTimelineStep =
  | { kind: "reasoning"; id: string; text: string }
  | { kind: "tool"; id: string; label: string; status: string; web: boolean }
  | { kind: "task"; id: string; label: string; status: string };

function isWebTool(name: string): boolean {
  return /web|search|browser/i.test(name);
}

function toolState(status: string): "input-available" | "output-available" | "output-error" {
  if (status === "in_progress") return "input-available";
  if (status === "failed") return "output-error";
  return "output-available";
}

/**
 * Rebuild the assistant's reasoning/tool chronology from a live run.
 * `run.events` carries one arrival marker per streamed part plus every item
 * (tool/task) update in sequence order, so walking it yields the true
 * interleaving between thinking segments and tool calls.
 */
export function buildLiveTimeline(run: LiveRun): AssistantTimelineStep[] {
  const steps: AssistantTimelineStep[] = [];
  const byId = new Map<string, AssistantTimelineStep>();
  const upsert = (step: AssistantTimelineStep): void => {
    const existing = byId.get(step.id);
    if (existing) {
      Object.assign(existing, step);
      return;
    }
    byId.set(step.id, step);
    steps.push(step);
  };

  for (const event of run.events) {
    if (event.version === 2 && event.item) {
      const item = event.item;
      const payload = item.payload;
      if (item.type === "reasoning_summary") {
        upsert({
          kind: "reasoning",
          id: `reasoning:${String(payload.partId ?? item.id)}`,
          text: "",
        });
      } else if (item.type === "tool_call") {
        const toolName = String(payload.toolName ?? payload.name ?? "工具");
        upsert({
          kind: "tool",
          id: item.id,
          label: String(payload.summary ?? toolName),
          status: item.status,
          web: isWebTool(toolName),
        });
      }
      // agent_task stays out of the live timeline: the run-activity panel
      // renders the richer delegation cards while the run is open.
    } else if (event.eventType === "message.part.insert" && event.payload.type === "reasoning") {
      const partId = String(event.payload.partId ?? "");
      if (partId) upsert({ kind: "reasoning", id: `reasoning:${partId}`, text: "" });
    }
  }

  for (const step of steps) {
    if (step.kind !== "reasoning") continue;
    const partId = step.id.slice("reasoning:".length);
    const part = run.parts.find((candidate) => candidate.id === partId);
    if (part?.type === "reasoning") step.text = part.text;
  }
  return steps;
}

/**
 * Rebuild the timeline for a stored message: reasoning segments come from the
 * persisted parts (in order); tool and delegation steps come from the run
 * trace. The trace carries no reasoning anchors, so reasoning leads.
 */
export function buildTraceTimeline(
  parts: RenderedMessagePart[],
  trace: Array<Record<string, unknown>>,
): AssistantTimelineStep[] {
  const reasoning: AssistantTimelineStep[] = parts
    .filter((part): part is Extract<RenderedMessagePart, { type: "reasoning" }> => part.type === "reasoning")
    .map((part) => ({ kind: "reasoning" as const, id: part.id, text: part.text }));
  const activity: AssistantTimelineStep[] = [];
  trace.forEach((entry, index) => {
    const performative = String(entry.performative ?? entry.type ?? "");
    if (performative === "tool_call" || performative === "skill_activate") {
      const toolName = String(entry.tool_name ?? entry.toolName ?? entry.name ?? entry.summary ?? "工具调用");
      activity.push({
        kind: "tool",
        id: `trace-${index}`,
        label: String(entry.summary ?? toolName),
        status: "completed",
        web: isWebTool(toolName),
      });
    } else if (performative === "delegate_task") {
      activity.push({
        kind: "task",
        id: `trace-${index}`,
        label: String(entry.task ?? entry.agent ?? entry.summary ?? "研究子任务"),
        status: "completed",
      });
    }
  });
  return [...reasoning, ...activity];
}

export function AssistantTimeline({
  steps,
  streaming = false,
  className,
}: {
  steps: AssistantTimelineStep[];
  streaming?: boolean;
  className?: string;
}) {
  if (!steps.length) return null;
  const lastIndex = steps.length - 1;
  return (
    <div className={cn("mb-3 space-y-2", className)}>
      {steps.map((step, index) => {
        if (step.kind === "reasoning") {
          const streamingNow = streaming && index === lastIndex;
          return (
            <Reasoning key={step.id} isStreaming={streamingNow}>
              <ReasoningTrigger
                getThinkingMessage={(active, duration) => active
                  ? "正在思考"
                  : duration
                    ? `思考了 ${duration} 秒`
                    : "思考过程"}
              />
              <ReasoningContent>{step.text || (streamingNow ? "…" : "")}</ReasoningContent>
            </Reasoning>
          );
        }
        return (
          <Tool key={step.id}>
            <ToolHeader
              title={step.label}
              type="dynamic-tool"
              state={toolState(step.status)}
              toolName={step.kind === "task" ? "委派任务" : "工具调用"}
            />
          </Tool>
        );
      })}
    </div>
  );
}
