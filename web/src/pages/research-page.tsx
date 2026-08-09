import { useParams } from "@tanstack/react-router";
import {
  Activity,
  BookOpen,
  Bot,
  ListTodo,
  PanelRightOpen,
  Sparkles,
  User,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { A2UIMindmap } from "@/components/a2ui-mindmap";
import { PageError } from "@/components/page-state";
import { ResearchInspector } from "@/components/research-inspector";
import {
  Message as AiMessage,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  ChainOfThought,
  ChainOfThoughtContent,
  ChainOfThoughtHeader,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
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
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger,
} from "@/components/ai-elements/sources";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  useMessages,
  useProject,
  useResumableRuns,
  useTurn,
} from "@/lib/queries";
import { consumeEventStream } from "@/lib/api";
import { applyA2UIEnvelope, type A2UISurface } from "@/lib/a2ui";
import { formatEvidenceCitations } from "@/lib/evidence";
import { summarizeRunActivity } from "@/lib/run-activity";
import { agentEventSchema, turnResultSchema } from "@/lib/schemas";
import type { AgentEvent, Message, TurnResult } from "@/lib/schemas";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

function MessageBubble({
  message,
  onInspect,
}: {
  message: Message;
  onInspect: (tab: "evidence" | "activity" | "plan") => void;
}) {
  const assistant = message.role === "assistant";
  const evidenceCount = message.evidence?.length ?? 0;
  const retrievedEvidenceCount =
    message.retrieved_evidence?.length ?? evidenceCount;
  const traceCount = message.trace?.length ?? 0;
  const renderedContent = assistant
    ? formatEvidenceCitations(message.content, message.evidence)
    : message.content;
  return (
    <div className={cn("flex gap-3", !assistant && "justify-end")}>
      {assistant && (
        <Avatar className="mt-1 size-8">
          <AvatarFallback>
            <Bot className="size-4" />
          </AvatarFallback>
        </Avatar>
      )}
      <AiMessage
        from={assistant ? "assistant" : "user"}
        className={cn(
          "min-w-0 max-w-[calc(100%-2.75rem)] sm:max-w-[86%]",
          !assistant && "order-first",
        )}
      >
        <MessageContent
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-7",
            assistant ? "bg-muted/55" : "bg-primary text-primary-foreground",
          )}
        >
          {assistant ? (
            <div
              onClick={(event) => {
                const citation = (
                  event.target as HTMLElement
                ).closest<HTMLAnchorElement>('a[href^="#evidence-"]');
                if (citation) {
                  event.preventDefault();
                  onInspect("evidence");
                }
              }}
            >
              <MessageResponse className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-pre:bg-background">
                {renderedContent}
              </MessageResponse>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </MessageContent>
        {assistant && <A2UIMindmap surface={message.a2ui} onInspectEvidence={() => onInspect("evidence")} />}
        {assistant && (evidenceCount > 0 || traceCount > 0 || message.plan) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(evidenceCount > 0 || retrievedEvidenceCount > 0) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onInspect("evidence")}
              >
                <BookOpen />
                {retrievedEvidenceCount} 条召回 · {evidenceCount} 条引用
              </Button>
            )}
            {traceCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onInspect("activity")}
              >
                <Activity />
                运行详情
              </Button>
            )}
            {message.plan && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onInspect("plan")}
              >
                <ListTodo />
                计划
              </Button>
            )}
          </div>
        )}
        {assistant && evidenceCount > 0 && (
          <Sources className="mt-3">
            <SourcesTrigger count={evidenceCount}>
              引用证据 · {evidenceCount}
            </SourcesTrigger>
            <SourcesContent>
              {message.evidence?.map((item, index) => (
                <Source
                  key={String(item.chunk_id ?? index)}
                  href={`#evidence-${String(item.chunk_id ?? index)}`}
                  title={String(item.doc_name ?? item.doc_uid ?? "项目文档")}
                  onClick={(event) => {
                    event.preventDefault();
                    onInspect("evidence");
                  }}
                />
              ))}
            </SourcesContent>
          </Sources>
        )}
      </AiMessage>
      {!assistant && (
        <Avatar className="mt-1 size-8">
          <AvatarFallback>
            <User className="size-4" />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}

function RunActivity({ events }: { events: AgentEvent[] }) {
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
    <div
      className="ml-11 max-w-[86%] space-y-3 py-1"
      role="status"
      aria-live="polite"
    >
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
              status={
                step.status === "failed"
                  ? "pending"
                  : step.status === "active"
                    ? "active"
                    : "complete"
              }
            >
              {step.toolName && (
                <Tool>
                  <ToolHeader
                    type="dynamic-tool"
                    toolName={step.toolName}
                    state={
                      step.status === "complete" || step.status === "failed"
                        ? "output-available"
                        : "input-available"
                    }
                  />
                  <ToolContent>
                    <ToolInput input={step.event.payload.arguments ?? {}} />
                    {step.status !== "active" && (
                      <ToolOutput
                        output={String(step.event.payload.summary ?? "")}
                        errorText={
                          step.status === "failed"
                            ? String(step.event.payload.summary ?? "处理失败")
                            : undefined
                        }
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
                <TaskTrigger
                  title={String(
                    todo.content ?? todo.title ?? todo.id ?? "未命名步骤",
                  )}
                />
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

type LiveRun = {
  events: AgentEvent[];
  answer: string;
  surface: A2UISurface | null;
};

function emptyLiveRun(): LiveRun {
  return { events: [], answer: "", surface: null };
}

function ResearchWorkspace({
  projectId,
  sessionId,
}: {
  projectId: string;
  sessionId: string;
}) {
  const project = useProject(projectId);
  const messages = useMessages(projectId, sessionId);
  const refetchMessages = messages.refetch;
  const resumableRuns = useResumableRuns(projectId, sessionId);
  const turn = useTurn(projectId, sessionId);
  const [lastTurn, setLastTurn] = useState<TurnResult>();
  const [liveRuns, setLiveRuns] = useState<Record<string, LiveRun>>({});
  const resumedRunIds = useRef(new Set<string>());
  const latestAssistant = useMemo(
    () =>
      [...(messages.data ?? [])]
        .reverse()
        .find((item) => item.role === "assistant"),
    [messages.data],
  );
  const openInspector = useUiStore((state) => state.openInspector);
  const liveEvents = useMemo(
    () => Object.values(liveRuns).flatMap((run) => run.events),
    [liveRuns],
  );
  const activeRuns = useMemo(() => Object.entries(liveRuns), [liveRuns]);
  const ensureLiveRun = useCallback((runId: string) => {
    setLiveRuns((current) =>
      current[runId] ? current : { ...current, [runId]: emptyLiveRun() },
    );
  }, []);
  const discardLiveRun = useCallback((runId: string) => {
    setLiveRuns((current) => {
      if (!current[runId]) return current;
      const remaining = { ...current };
      delete remaining[runId];
      return remaining;
    });
  }, []);
  const handleRunEvent = useCallback((event: AgentEvent) => {
    setLiveRuns((current) => {
      const run = current[event.runId] ?? emptyLiveRun();
      if (event.eventType === "answer.delta")
        return {
          ...current,
          [event.runId]: {
            ...run,
            answer: run.answer + String(event.payload.text ?? ""),
          },
        };
      if (event.eventType === "ui.a2ui")
        return {
          ...current,
          [event.runId]: {
            ...run,
            surface: applyA2UIEnvelope(run.surface, event.payload.envelope),
          },
        };
      if (run.events.some((item) => item.eventId === event.eventId))
        return current;
      return {
        ...current,
        [event.runId]: { ...run, events: [...run.events, event] },
      };
    });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    for (const run of resumableRuns.data ?? []) {
      if (resumedRunIds.current.has(run.run_uid)) continue;
      resumedRunIds.current.add(run.run_uid);
      ensureLiveRun(run.run_uid);
      void consumeEventStream(
        `/runs/${run.run_uid}/events?afterSeq=0`,
        (rawEvent) => {
          const event = agentEventSchema.parse(rawEvent);
          handleRunEvent(event);
          if (event.eventType === "run.completed") {
            setLastTurn(turnResultSchema.parse(event.payload.result));
            void refetchMessages().finally(() => discardLiveRun(event.runId));
          }
          if (event.eventType === "run.failed") {
            void refetchMessages().finally(() => discardLiveRun(event.runId));
          }
        },
        controller.signal,
      ).catch((error: unknown) => {
        if (controller.signal.aborted) return;
        toast.error(
          error instanceof Error ? error.message : "未能恢复进行中的研究",
        );
      });
    }
    return () => controller.abort();
  }, [
    discardLiveRun,
    ensureLiveRun,
    handleRunEvent,
    refetchMessages,
    resumableRuns.data,
  ]);
  useEffect(() => {
    if (!messages.data) return;
    const frame = requestAnimationFrame(() =>
      document
        .getElementById("conversation-end")
        ?.scrollIntoView({ behavior: "smooth" }),
    );
    return () => cancelAnimationFrame(frame);
  }, [messages.data, activeRuns.length, liveEvents.length]);
  const submit = async (prompt: string) => {
    const normalizedPrompt = prompt.trim();
    if (!normalizedPrompt || normalizedPrompt.length > 100_000) return;
    if (turn.isPending) return;
    let createdRunId = "";
    try {
      setLastTurn(
        await turn.mutateAsync({
          prompt: normalizedPrompt,
          onRunCreated: (runId) => {
            createdRunId = runId;
            resumedRunIds.current.add(runId);
            ensureLiveRun(runId);
          },
          onEvent: handleRunEvent,
        }),
      );
      if (createdRunId) discardLiveRun(createdRunId);
    } catch (error) {
      if (createdRunId) discardLiveRun(createdRunId);
      toast.error(error instanceof Error ? error.message : "发送失败");
    }
  };
  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col overflow-hidden md:h-full">
      <div className="min-h-0 flex flex-1 overflow-hidden">
        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex h-14 shrink-0 items-center justify-between border-b px-5 lg:px-8">
            <p className="truncate text-sm font-medium">
              {project.data?.project_name ?? "研究工作区"}
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => openInspector("activity")}
            >
              <PanelRightOpen />
              详情
            </Button>
          </div>
          <Conversation className="min-h-0">
            <ConversationContent className="mx-auto w-full max-w-3xl gap-7 px-4 py-8 lg:px-8">
              {messages.error ? (
                <PageError error={messages.error} />
              ) : messages.isLoading ? (
                <p className="text-sm text-muted-foreground">加载会话…</p>
              ) : !messages.data?.length ? (
                <ConversationEmptyState
                  title="从一个好问题开始"
                  description="系统会按需查阅项目资料，并附上可核对的引用。"
                  icon={<Sparkles className="size-6" />}
                />
              ) : (
                messages.data.map((message, index) => (
                  <MessageBubble
                    key={index}
                    message={message}
                    onInspect={openInspector}
                  />
                ))
              )}
              {activeRuns.map(([runId, run]) => (
                <div key={runId}>
                  <RunActivity events={run.events} />
                  {run.answer && (
                    <MessageBubble
                      message={{
                        role: "assistant",
                        content: run.answer,
                        a2ui: run.surface
                          ? {
                              catalogId: run.surface.catalogId,
                              surfaceId: run.surface.surfaceId,
                              mindmap: run.surface.mindmap,
                            }
                          : null,
                      }}
                      onInspect={openInspector}
                    />
                  )}
                </div>
              ))}
              <div id="conversation-end" />
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
          <div className="shrink-0 border-t bg-background p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] lg:p-5">
            <PromptInput
              className="mx-auto max-w-3xl"
              onSubmit={({ text }) => submit(text)}
            >
              <PromptInputBody>
                <PromptInputTextarea
                  disabled={turn.isPending || activeRuns.length > 0}
                  placeholder="询问论文、比较方法，或开展一项研究任务…"
                />
              </PromptInputBody>
              <PromptInputFooter>
                <span className="text-[11px] text-muted-foreground">
                  Enter 发送 · Shift + Enter 换行 · 回答可能需要核对原始证据
                </span>
                <PromptInputSubmit
                  disabled={turn.isPending || activeRuns.length > 0}
                  status={
                    turn.isPending || activeRuns.length > 0
                      ? "submitted"
                      : "ready"
                  }
                />
              </PromptInputFooter>
            </PromptInput>
          </div>
        </main>
      </div>
      <ResearchInspector
        projectId={projectId}
        turn={lastTurn}
        latest={latestAssistant}
        liveEvents={liveEvents}
      />
    </div>
  );
}

export function ResearchPage() {
  const { projectId, sessionId } = useParams({ strict: false }) as {
    projectId: string;
    sessionId: string;
  };

  return (
    <ResearchWorkspace
      key={`${projectId}:${sessionId}`}
      projectId={projectId}
      sessionId={sessionId}
    />
  );
}
