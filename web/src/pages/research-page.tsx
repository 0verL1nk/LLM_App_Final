import { useNavigate, useParams } from "@tanstack/react-router";
import { PanelRightOpen, Sparkles } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import type { ExecutionMode } from "@/components/mode-selector";
import { MessageBubble } from "@/components/message-bubble";
import { PageError } from "@/components/page-state";
import { ResearchComposer } from "@/components/research-composer";
import {
  buildLiveTimeline,
} from "@/components/assistant-run-timeline";
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
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
import {
  useCreateSession,
  useMessages,
  useRenameSession,
  useSessionCommand,
  useSessionSuggestions,
  useProject,
  useResumableRuns,
  useSteeringInput,
  useTurn,
} from "@/lib/queries";
import { sessionContextUsage } from "@/lib/context-usage";
import { consumeEventStream } from "@/lib/api";
import {
  createLiveRun,
  liveAnswer,
  reduceLiveRun,
  type LiveRun,
} from "@/lib/live-run";
import { agentEventSchema, turnResultSchema } from "@/lib/schemas";
import type { AgentEvent, TurnResult } from "@/lib/schemas";
import { useUiStore } from "@/stores/ui-store";

const ResearchInspector = lazy(async () => {
  const module = await import("@/components/research-inspector");
  return { default: module.ResearchInspector };
});

const ResearchRunActivity = lazy(async () => {
  const module = await import("@/components/research-run-activity");
  return { default: module.ResearchRunActivity };
});

function ResearchWorkspace({
  projectId,
  sessionId,
}: {
  projectId: string;
  sessionId: string;
}) {
  const project = useProject(projectId);
  const messages = useMessages(projectId, sessionId);
  const suggestionCount = messages.data?.length ?? 0;
  const suggestions = useSessionSuggestions(projectId, sessionId, suggestionCount);
  const suggestionItems = suggestions.data?.suggestions ?? [];
  const refetchMessages = messages.refetch;
  const resumableRuns = useResumableRuns(projectId, sessionId);
  const turn = useTurn(projectId, sessionId);
  const steeringInput = useSteeringInput(projectId, sessionId);
  const sessionCommand = useSessionCommand(projectId, sessionId);
  const createSession = useCreateSession(projectId);
  const renameSession = useRenameSession(projectId, sessionId);
  const navigate = useNavigate();
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("auto");
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
  const contextUsage = sessionContextUsage(
    lastTurn?.context_snapshot ?? latestAssistant?.context_snapshot,
  );
  const inspectorOpen = useUiStore((state) => state.inspectorOpen);
  const openInspector = useUiStore((state) => state.openInspector);
  const liveEvents = useMemo(
    () => Object.values(liveRuns).flatMap((run) => run.events),
    [liveRuns],
  );
  const activeRuns = useMemo(() => Object.entries(liveRuns), [liveRuns]);
  const ensureLiveRun = useCallback((runId: string) => {
    setLiveRuns((current) =>
      current[runId] ? current : { ...current, [runId]: createLiveRun() },
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
      const run = current[event.runId] ?? createLiveRun();
      const next = reduceLiveRun(run, event);
      return next === run ? current : { ...current, [event.runId]: next };
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
    if (activeRuns.length > 0) {
      try {
        await steeringInput.mutateAsync(normalizedPrompt);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "未能加入运行中队列");
      }
      return;
    }
    let createdRunId = "";
    try {
      setLastTurn(
        await turn.mutateAsync({
          prompt: normalizedPrompt,
          executionMode,
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
  const executeCommand = async (command: string, args: string) => {
    if (command === "compact" && activeRuns.length > 0) {
      toast.error("有进行中的研究运行，请等待完成后再压缩会话上下文");
      return;
    }
    if (command === "new") {
      try {
        const created = await createSession.mutateAsync("新探索");
        await navigate({
          to: "/projects/$projectId/research/$sessionId",
          params: { projectId, sessionId: created.session_uid },
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "创建探索失败");
      }
      return;
    }
    if (command === "rename") {
      const sessionName = args.trim();
      if (!sessionName) {
        toast.error("用法：/rename 新名称");
        return;
      }
      try {
        await renameSession.mutateAsync(sessionName);
        toast.success(`会话已重命名为「${sessionName}」`);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "重命名失败");
      }
      return;
    }
    try {
      await sessionCommand.mutateAsync({ command, args });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "命令执行失败");
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
                  {run.events.length === 0 && (
                    <Queue className="mx-auto mb-4 max-w-3xl">
                      <QueueSection defaultOpen>
                        <QueueSectionTrigger>
                          <QueueSectionLabel label="研究运行已创建" />
                        </QueueSectionTrigger>
                        <QueueSectionContent>
                          <QueueList>
                            <QueueItem>
                              <div className="flex items-start gap-2">
                                <QueueItemIndicator />
                                <QueueItemContent>等待服务端首个运行事件</QueueItemContent>
                              </div>
                            </QueueItem>
                          </QueueList>
                        </QueueSectionContent>
                      </QueueSection>
                    </Queue>
                  )}
                  {(run.events.length > 0 || run.parts.length > 0 || Object.keys(run.items).length > 0) && (
                    <Suspense fallback={null}>
                      <MessageBubble
                        message={{
                          role: "assistant",
                          content: liveAnswer(run.parts),
                          parts: run.parts,
                          a2ui: Object.values(run.surfaces).map((surface) => ({
                            catalogId: surface.catalogId,
                            surfaceId: surface.surfaceId,
                            title: surface.title,
                            mindmap: surface.mindmap,
                          })),
                        }}
                        onInspect={openInspector}
                        activity={<ResearchRunActivity items={Object.values(run.items)} />}
                        timeline={buildLiveTimeline(run)}
                        isStreaming
                      />
                    </Suspense>
                  )}
                </div>
              ))}
              <div id="conversation-end" />
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
          <div className="shrink-0 border-t bg-background p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] lg:p-5">
            <ResearchComposer
              inputDisabled={turn.isPending}
              submitStatus={turn.isPending ? "submitted" : "ready"}
              suggestions={suggestionItems}
              showSuggestions={!turn.isPending && activeRuns.length === 0}
              executionMode={executionMode}
              onExecutionModeChange={setExecutionMode}
              modeDisabled={turn.isPending || activeRuns.length > 0}
              contextUsage={contextUsage}
              onPromptSubmit={submit}
              onCommand={executeCommand}
            />
          </div>
        </main>
      </div>
      {inspectorOpen && (
        <Suspense fallback={null}>
          <ResearchInspector projectId={projectId} sessionId={sessionId}
            turn={lastTurn}
            latest={latestAssistant}
            liveEvents={liveEvents}
          />
        </Suspense>
      )}
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
