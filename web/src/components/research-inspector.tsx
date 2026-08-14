import {
  Activity,
  BookOpen,
  ChevronDown,
  FileText,
  MapPin,
  Scale,
} from "lucide-react";

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
} from "@/components/ai-elements/tool";
import { MessageResponse } from "@/components/ai-elements/message";
import { EvidencePreview } from "@/components/evidence-preview";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { AgentEvent, Message, ResearchArtifact, TurnResult } from "@/lib/schemas";
import { useResearchArtifacts } from "@/lib/queries";
import {
  latestPlanTodos,
  normalizeResearchTodos,
  summarizeToolExecutions,
  type ResearchTodo,
} from "@/lib/research-activity-details";
import { useUiStore } from "@/stores/ui-store";

type Evidence = Record<string, unknown>;

type ResearchInspectorProps = {
  projectId: string;
  sessionId: string;
  turn?: TurnResult;
  latest?: Message;
  liveEvents: AgentEvent[];
};

function asRecords(value: unknown): Evidence[] {
  return Array.isArray(value)
    ? value.filter(
        (item): item is Evidence => Boolean(item) && typeof item === "object",
      )
    : [];
}

function locationLabel(evidence: Evidence): string | null {
  const pages = new Set<number>();
  if (typeof evidence.page_no === "number") pages.add(evidence.page_no);
  for (const location of asRecords(evidence.ocr_locations)) {
    if (typeof location.page_no === "number") pages.add(location.page_no);
  }
  if (!pages.size) return null;

  const pageText = [...pages]
    .sort((left, right) => left - right)
    .map((page) => `第 ${page} 页`)
    .join("、");
  const locationCount = asRecords(evidence.ocr_locations).length;
  return locationCount > 1 ? `${pageText} · ${locationCount} 处定位` : pageText;
}

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

function toolTitle(toolName: string): string {
  return {
    search_document: "检索资料",
    read_document: "阅读原文",
    list_document: "查看资料库",
    web_search: "检索网页",
  }[toolName] ?? toolName;
}

function ResearchPlan({
  plan,
  todos,
}: {
  plan: Evidence | null | undefined;
  todos: ResearchTodo[];
}) {
  const goal = typeof plan?.goal === "string" ? plan.goal.trim() : "";
  const description = typeof plan?.description === "string" ? plan.description.trim() : "";
  if (!goal && !description && !todos.length) return null;

  return (
    <Plan defaultOpen>
      <PlanHeader className="px-4 py-3">
        <div className="space-y-1">
          <PlanTitle>研究计划</PlanTitle>
          <PlanDescription>
            {goal || description || `已记录 ${todos.length} 项任务`}
          </PlanDescription>
        </div>
        <PlanTrigger aria-label="展开或收起研究计划" />
      </PlanHeader>
      <PlanContent className="space-y-4 px-4 pb-4">
        {description && <p className="text-sm leading-6 text-muted-foreground">{description}</p>}
        {todos.length > 0 && (
          <div className="space-y-3">
            {todos.map((todo) => (
              <Task key={todo.id} defaultOpen={todo.status === "in_progress"}>
                <TaskTrigger title={todo.content}>
                  <div className="flex w-full cursor-pointer items-center justify-between gap-3 text-left text-sm">
                    <span>{todo.content}</span>
                    <Badge variant="secondary">{todoStatusLabel(todo.status)}</Badge>
                  </div>
                </TaskTrigger>
                {todo.dependsOn.length > 0 && (
                  <TaskContent>
                    <TaskItem>依赖任务：{todo.dependsOn.join("、")}</TaskItem>
                  </TaskContent>
                )}
              </Task>
            ))}
          </div>
        )}
      </PlanContent>
    </Plan>
  );
}

function DetailSection({
  icon: Icon,
  title,
  count,
  children,
}: {
  icon: typeof BookOpen;
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="size-4 text-primary" />
          {title}
        </h3>
        {count !== undefined && <Badge variant="secondary">{count}</Badge>}
      </div>
      {children}
    </section>
  );
}

function EvidenceCard({
  evidence,
  projectId,
  cited,
}: {
  evidence: Evidence;
  projectId: string;
  cited: boolean;
}) {
  const location = locationLabel(evidence);
  return (
    <Card
      id={cited ? `evidence-${String(evidence.chunk_id ?? "")}` : undefined}
      className="overflow-hidden border-border/80 bg-card shadow-sm"
    >
      <div className="flex items-start gap-3 p-4">
        <div className="mt-0.5 rounded-md bg-primary/10 p-2 text-primary">
          <FileText className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {String(evidence.doc_name ?? evidence.doc_uid ?? "项目文档")}
          </p>
          {location && (
            <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="size-3" />
              {location}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {cited && <Badge>已引用</Badge>}
          <EvidencePreview projectId={projectId} evidence={evidence} />
        </div>
      </div>
      <p className="border-t bg-muted/15 px-4 py-3 text-sm leading-6 text-muted-foreground">
        {String(evidence.text ?? "")}
      </p>
    </Card>
  );
}

function EvidenceMerge({ artifact, projectId }: { artifact: ResearchArtifact; projectId: string }) {
  const content = artifact.content;
  const claims = asRecords(content.claims);
  const conflicts = asRecords(content.conflicts);
  const evidence = asRecords(content.evidence);
  const openQuestions = Array.isArray(content.open_questions) ? content.open_questions.filter((item): item is string => typeof item === "string") : [];
  const summaries = asRecords(content.packet_summaries);
  if (!claims.length && !conflicts.length && !openQuestions.length && !summaries.length) return null;
  return (
    <DetailSection icon={Scale} title="跨任务证据合并" count={claims.length}>
      <div className="space-y-3">
        {conflicts.length > 0 && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <p className="font-medium">发现 {conflicts.length} 组待裁决矛盾</p>
            <p className="mt-1 text-muted-foreground">系统保留双方主张及来源，等待 Leader 基于证据明确判断。</p>
          </div>
        )}
        {claims.map((claim) => (
          <div key={String(claim.claim_id)} className="rounded-lg border bg-muted/20 p-3">
            <p className="text-sm leading-6">{String(claim.statement ?? "未命名主张")}</p>
            <p className="mt-1 text-xs text-muted-foreground">{String(claim.role ?? "unknown")} · {String(claim.task_uid ?? "")}</p>
            {Array.isArray(claim.evidence_refs) && claim.evidence_refs.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">证据：{claim.evidence_refs.map(String).join("、")}</p>
            )}
          </div>
        ))}
        {evidence.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {evidence.map((reference) => (
              <EvidencePreview key={String(reference.chunk_id)} projectId={projectId} evidence={reference} />
            ))}
          </div>
        )}
        {openQuestions.length > 0 && <p className="text-sm text-muted-foreground">待解问题：{openQuestions.join("；")}</p>}
        {summaries.map((summary) => (
          <MessageResponse key={String(summary.task_uid)}>{String(summary.summary ?? "")}</MessageResponse>
        ))}
      </div>
    </DetailSection>
  );
}

export function ResearchInspector({
  projectId,
  sessionId,
  turn,
  latest,
  liveEvents,
}: ResearchInspectorProps) {
  const store = useUiStore();
  const researchArtifacts = useResearchArtifacts(projectId, sessionId);
  const citedEvidence = asRecords(turn?.evidence_items ?? latest?.evidence);
  const retrievedEvidence = asRecords(
    turn?.retrieved_evidence_items ?? latest?.retrieved_evidence,
  );
  const citedIds = new Set(
    citedEvidence.map((item) => String(item.chunk_id ?? "")),
  );
  const candidates = retrievedEvidence.filter(
    (item) => !citedIds.has(String(item.chunk_id ?? "")),
  );
  const liveTrace = liveEvents.flatMap((event) =>
    event.payload.trace ? [event.payload.trace as Evidence] : [],
  );
  const trace = liveTrace.length
    ? liveTrace
    : (turn?.trace_payload ?? latest?.trace ?? []);
  const plan = turn?.agent_plan ?? turn?.plan ?? latest?.plan;
  const context = turn?.context_snapshot ?? latest?.context_snapshot;
  const scope = context?.project_scope as Evidence | undefined;
  const memories = asRecords(context?.memory_items);
  const todos = normalizeResearchTodos(turn?.todos);
  const plannedTodos = todos.length ? todos : latestPlanTodos(liveEvents);
  const toolExecutions = summarizeToolExecutions(liveEvents);
  const latestMerge = [...(researchArtifacts.data ?? [])].reverse().find((artifact) => artifact.artifact_type === "evidence_merge");

  return (
    <Sheet open={store.inspectorOpen} onOpenChange={store.setInspectorOpen}>
      <SheetContent className="flex w-full flex-col gap-0 overflow-hidden border-l p-0 sm:max-w-[30rem]">
        <SheetHeader className="border-b bg-muted/20 px-6 py-5 text-left">
          <SheetTitle>研究详情</SheetTitle>
          <SheetDescription className="mt-1">
            本次回答的引用依据、过程与资料范围。
          </SheetDescription>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {[
              [citedEvidence.length, "已引用"],
              [retrievedEvidence.length, "召回资料"],
              [trace.length, "活动记录"],
            ].map(([value, label]) => (
              <div
                key={String(label)}
                className="rounded-lg border bg-background px-3 py-2"
              >
                <p className="text-lg font-semibold tabular-nums">{value}</p>
                <p className="text-xs text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
        </SheetHeader>

        <div className="min-h-0 flex-1 space-y-7 overflow-y-auto px-5 py-6">
          <DetailSection
            icon={BookOpen}
            title="引用证据"
            count={citedEvidence.length}
          >
            {citedEvidence.length ? (
              <div className="space-y-3">
                {citedEvidence.map((evidence, index) => (
                  <EvidenceCard
                    key={String(evidence.chunk_id ?? index)}
                    evidence={evidence}
                    projectId={projectId}
                    cited
                  />
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed px-4 py-5 text-sm text-muted-foreground">
                这次回答没有引用项目资料。
              </p>
            )}
          </DetailSection>

          {candidates.length > 0 && (
            <Collapsible>
              <CollapsibleTrigger className="flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left text-sm font-medium transition-colors hover:bg-muted/50">
                <span>继续查看 {candidates.length} 条相关资料</span>
                <ChevronDown className="size-4 text-muted-foreground" />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {candidates.map((evidence, index) => (
                  <EvidenceCard
                    key={String(evidence.chunk_id ?? index)}
                    evidence={evidence}
                    projectId={projectId}
                    cited={false}
                  />
                ))}
              </CollapsibleContent>
            </Collapsible>
          )}

          <ResearchPlan plan={plan} todos={plannedTodos} />

          {latestMerge && <EvidenceMerge artifact={latestMerge} projectId={projectId} />}

          {toolExecutions.length > 0 && (
            <DetailSection icon={Activity} title="已使用的工具" count={toolExecutions.length}>
              <div className="space-y-2">
                {toolExecutions.map((tool) => (
                  <Tool key={tool.actionId} defaultOpen={tool.status === "failed"}>
                    <ToolHeader
                      type="dynamic-tool"
                      toolName={tool.toolName}
                      title={toolTitle(tool.toolName)}
                      state={tool.status === "active" ? "input-available" : tool.status === "failed" ? "output-error" : "output-available"}
                    />
                    <ToolContent>
                      {tool.summary ? (
                        <p className="text-sm leading-6 text-muted-foreground">{tool.summary}</p>
                      ) : (
                        <p className="text-sm text-muted-foreground">{tool.status === "active" ? "正在处理" : "本次调用未返回可展示的摘要。"}</p>
                      )}
                      {tool.durationMs !== undefined && (
                        <p className="text-xs text-muted-foreground">耗时 {(tool.durationMs / 1000).toFixed(1)} 秒</p>
                      )}
                    </ToolContent>
                  </Tool>
                ))}
              </div>
            </DetailSection>
          )}

          <DetailSection icon={Activity} title="工作过程" count={trace.length}>
            {trace.length ? (
              <div className="space-y-2">
                {trace.map((item, index) => (
                  <div
                    key={index}
                    className="rounded-lg border bg-muted/20 px-3 py-2.5"
                  >
                    <Badge variant="secondary" className="text-[11px]">
                      {String(item.phase ?? item.performative ?? "处理")}
                    </Badge>
                    {String(item.content ?? item.summary ?? "").trim() && (
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {String(item.content ?? item.summary ?? "")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                本轮没有需要展开的工作记录。
              </p>
            )}
          </DetailSection>

          <section className="rounded-xl border bg-muted/20 p-4">
            <p className="text-sm font-medium">资料与记忆范围</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              本轮可检索 {Number(scope?.ready_document_count ?? 0)}{" "}
              份已解析资料，内容会按问题按需检索。
            </p>
            {memories.length > 0 && (
              <div className="mt-3 border-t pt-3">
                <p className="text-xs font-medium text-muted-foreground">
                  已使用的长期记忆
                </p>
                {memories.map((item, index) => (
                  <p
                    key={index}
                    className="mt-2 text-sm leading-6 text-muted-foreground"
                  >
                    <span className="mr-1 text-xs uppercase">{String(item.memory_type ?? "memory")}</span>
                    {String(item.content ?? "")}
                  </p>
                ))}
              </div>
            )}
          </section>
        </div>
      </SheetContent>
    </Sheet>
  );
}
