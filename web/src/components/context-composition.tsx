import {
  Context,
  ContextContent,
  ContextContentBody,
  ContextContentHeader,
  ContextTrigger,
} from "@/components/ai-elements/context";
import type { SessionContextUsage } from "@/lib/context-usage";
import { cn } from "@/lib/utils";

const SEGMENT_COLORS = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4", "bg-chart-5"] as const;

function segmentPercent(segment: { tokens: number }, maxTokens: number): number {
  if (maxTokens <= 0) return 0;
  return Math.min(100, (segment.tokens / maxTokens) * 100);
}

export function ContextCompositionCard({ usage }: { usage: SessionContextUsage }) {
  return (
    <Context maxTokens={usage.maxTokens} usedTokens={usage.usedTokens}>
      <ContextTrigger aria-label="查看会话上下文容量" />
      <ContextContent align="end">
        <ContextContentHeader />
        <ContextContentBody className="space-y-2 text-xs text-muted-foreground">
          <div
            className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
            role="img"
            aria-label="上下文构成"
          >
            {usage.segments.map((segment, index) => {
              const percent = segmentPercent(segment, usage.maxTokens);
              if (percent <= 0) return null;
              return (
                <div
                  key={segment.key}
                  className={cn("h-full", SEGMENT_COLORS[index % SEGMENT_COLORS.length])}
                  style={{ width: `${percent}%` }}
                />
              );
            })}
          </div>
          <ul className="space-y-1">
            {usage.segments.map((segment, index) => (
              <li key={segment.key} className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className={cn("size-2 shrink-0 rounded-[2px]", SEGMENT_COLORS[index % SEGMENT_COLORS.length])} />
                  <span className="truncate">{segment.label}</span>
                </span>
                <span className="shrink-0 tabular-nums">
                  {segment.tokens.toLocaleString()} · {Math.round(segmentPercent(segment, usage.maxTokens))}%
                </span>
              </li>
            ))}
          </ul>
          <p>服务端基于当前会话、系统提示和工具定义计算。</p>
        </ContextContentBody>
      </ContextContent>
    </Context>
  );
}
