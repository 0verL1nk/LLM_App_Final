import {
  Activity,
  BookOpen,
  Bot,
  ListTodo,
  User,
} from "lucide-react";
import { useMemo, type ReactNode } from "react";

import { A2UIMindmap } from "@/components/a2ui-mindmap";
import { ResearchOrbs } from "@/components/agent-status";
import { EvidenceCitations } from "@/components/evidence-citations";
import { CitationContext, evidenceMarkdownComponents } from "@/components/evidence-inline-citations";
import {
  AssistantTimeline,
  buildTraceTimeline,
  type AssistantTimelineStep,
} from "@/components/assistant-run-timeline";
import {
  Message as AiMessage,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { assistantParts } from "@/lib/live-run";
import { formatEvidenceCitations } from "@/lib/evidence";
import type { Message } from "@/lib/schemas";
import { cn } from "@/lib/utils";

export interface MessageBubbleProps {
  message: Message;
  onInspect: (tab: "evidence" | "activity" | "plan") => void;
  activity?: ReactNode;
  timeline?: AssistantTimelineStep[];
  isStreaming?: boolean;
}

export function MessageBubble({
  message,
  onInspect,
  activity,
  timeline,
  isStreaming = false,
}: MessageBubbleProps) {
  const assistant = message.role === "assistant";
  const evidenceCount = message.evidence?.length ?? 0;
  const retrievedEvidenceCount =
    message.retrieved_evidence?.length ?? evidenceCount;
  const traceCount = message.trace?.length ?? 0;
  const renderedContent = assistant
    ? formatEvidenceCitations(message.content, message.evidence)
    : message.content;
  const surfaces = (Array.isArray(message.a2ui) ? message.a2ui : [message.a2ui])
    .filter((surface): surface is Record<string, unknown> => Boolean(surface && typeof surface === "object"))
    .reduce<Record<string, Record<string, unknown>>>((items, surface, index) => {
      items[typeof surface.surfaceId === "string" ? surface.surfaceId : `surface-${index}`] = surface;
      return items;
    }, {});
  const parts = assistant ? assistantParts(message) : [];
  const timelineSteps =
    timeline ?? (assistant ? buildTraceTimeline(parts, message.trace ?? []) : []);
  const isWaitingForFirstPart = isStreaming && !parts.length;
  const citationValue = useMemo(
    () => ({ evidence: message.evidence ?? [], onInspect: () => onInspect("evidence") }),
    [message.evidence, onInspect],
  );
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
              {isWaitingForFirstPart && <ResearchOrbs />}
              <AssistantTimeline steps={timelineSteps} streaming={isStreaming} />
              {activity}
              <CitationContext.Provider value={citationValue}>
                {parts.map((part) => {
                  if (part.type === "markdown") {
                    const content = part.text === message.content ? renderedContent : formatEvidenceCitations(part.text, message.evidence);
                    return <MessageResponse key={part.id} className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-pre:bg-background" components={evidenceMarkdownComponents}>{content}</MessageResponse>;
                  }
                  if (part.type === "reasoning") return null;
                  const surface = part.surfaceId ? surfaces[part.surfaceId] : undefined;
                  return surface ? (
                    <A2UIMindmap key={part.id} surface={surface} onInspectEvidence={() => onInspect("evidence")} />
                  ) : isStreaming ? (
                    <div key={part.id} className="my-3 h-20 animate-pulse rounded-xl border bg-background/60" aria-label="正在生成可视化梳理" />
                  ) : (
                    <p key={part.id} className="my-2 text-xs text-muted-foreground">
                      这条回复包含一张思维导图，但生成时未通过校验；正文中的文字版仍然可用。
                    </p>
                  );
                })}
              </CitationContext.Provider>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </MessageContent>
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
        {assistant && evidenceCount > 0 && <EvidenceCitations evidence={message.evidence ?? []} onInspect={() => onInspect("evidence")} />}
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
