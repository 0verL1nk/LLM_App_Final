import {
  Context,
  ContextContent,
  ContextContentBody,
  ContextContentHeader,
  ContextTrigger,
} from "@/components/ai-elements/context";
import type { SessionContextUsage } from "@/lib/context-usage";
import { cn } from "@/lib/utils";

// Validated categorical palette (dataviz method): fixed order, distinct hues,
// separate steps for dark surfaces; legend labels carry identity where
// light-mode contrast is below 3:1.
const SEGMENT_COLORS = [
  "bg-[#2a78d6] dark:bg-[#3987e5]",
  "bg-[#eb6834] dark:bg-[#d95926]",
  "bg-[#1baf7a] dark:bg-[#199e70]",
  "bg-[#eda100] dark:bg-[#c98500]",
  "bg-[#e87ba4] dark:bg-[#d55181]",
] as const;

// Free space renders as the neutral track and the summarization trigger as a
// marker line, so neither participates in the categorical coloring.
const FREE_SPACE_KEY = "free_space";
const SUMMARIZATION_KEY = "summarization_buffer_estimate";

const SEGMENT_LABELS: Record<string, string> = {
  system_prompt: "系统提示",
  custom_agents: "子代理清单",
  tools: "工具定义",
  messages: "会话消息",
  [FREE_SPACE_KEY]: "剩余空间",
  [SUMMARIZATION_KEY]: "总结触发线",
};

function segmentLabel(key: string, fallback: string): string {
  return SEGMENT_LABELS[key] ?? fallback;
}

function windowPercent(tokens: number, maxTokens: number): number {
  if (maxTokens <= 0) return 0;
  return Math.min(100, (tokens / maxTokens) * 100);
}

export function ContextCompositionCard({ usage }: { usage: SessionContextUsage }) {
  const contentSegments = usage.segments.filter(
    (segment) => segment.key !== FREE_SPACE_KEY && segment.key !== SUMMARIZATION_KEY,
  );
  const freeSpace = usage.segments.find((segment) => segment.key === FREE_SPACE_KEY);
  const buffer = usage.segments.find((segment) => segment.key === SUMMARIZATION_KEY);
  // The buffer spans [used, trigger], so its width marks where summarization
  // kicks in on the model-window scale.
  const triggerPercent =
    buffer && usage.maxTokens > 0
      ? windowPercent(buffer.tokens + usage.usedTokens, usage.maxTokens)
      : null;

  return (
    <Context maxTokens={usage.maxTokens} usedTokens={usage.usedTokens}>
      <ContextTrigger aria-label="查看会话上下文容量" />
      <ContextContent align="end">
        <ContextContentHeader />
        <ContextContentBody className="space-y-2 text-xs text-muted-foreground">
          <div className="relative h-2 w-full rounded-[4px] bg-muted" role="img" aria-label="上下文构成">
            <div className="flex h-full w-full gap-[2px] overflow-hidden rounded-[4px]">
              {contentSegments.map((segment, index) => {
                const percent = windowPercent(segment.tokens, usage.maxTokens);
                if (percent <= 0) return null;
                return (
                  <div
                    key={segment.key}
                    className={cn("h-full flex-none", SEGMENT_COLORS[index % SEGMENT_COLORS.length])}
                    style={{ width: `${percent}%` }}
                  />
                );
              })}
            </div>
            {triggerPercent !== null && triggerPercent <= 100 && (
              <span
                aria-hidden
                className="absolute inset-y-[-3px] w-0 border-l-2 border-dashed border-muted-foreground/60"
                style={{ left: `${triggerPercent}%` }}
                title="总结触发线"
              />
            )}
          </div>
          <ul className="space-y-1">
            {contentSegments.map((segment, index) => (
              <li key={segment.key} className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className={cn("size-2 shrink-0 rounded-[2px]", SEGMENT_COLORS[index % SEGMENT_COLORS.length])} />
                  <span className="truncate">{segmentLabel(segment.key, segment.label)}</span>
                </span>
                <span className="shrink-0 tabular-nums">
                  {segment.tokens.toLocaleString()} · {Math.round(windowPercent(segment.tokens, usage.maxTokens))}%
                </span>
              </li>
            ))}
            {freeSpace && freeSpace.tokens > 0 && (
              <li className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className="size-2 shrink-0 rounded-[2px] bg-muted" />
                  <span className="truncate">{segmentLabel(freeSpace.key, freeSpace.label)}</span>
                </span>
                <span className="shrink-0 tabular-nums">{freeSpace.tokens.toLocaleString()}</span>
              </li>
            )}
            {triggerPercent !== null && (
              <li className="flex items-center gap-1.5">
                <span aria-hidden className="inline-block h-2.5 border-l-2 border-dashed border-muted-foreground/60" />
                <span>总结触发线</span>
              </li>
            )}
          </ul>
        </ContextContentBody>
      </ContextContent>
    </Context>
  );
}
