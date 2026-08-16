import { ChevronDown } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export const EXECUTION_MODES = [
  { value: "auto", label: "自动" },
  { value: "react", label: "ReAct" },
  { value: "plan_execute", label: "计划执行" },
  { value: "agent_teams", label: "团队协作" },
] as const;

export type ExecutionMode = (typeof EXECUTION_MODES)[number]["value"];

/**
 * Compact indicator of the active research mode; clicking it pops the
 * sliding segmented switch. Matches the prompt toolbar's ghost controls.
 */
export function ModeSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: ExecutionMode;
  onChange: (mode: ExecutionMode) => void;
  disabled?: boolean;
}) {
  const activeIndex = EXECUTION_MODES.findIndex((mode) => mode.value === value);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          aria-label="本轮研究模式"
          className={cn(
            "flex h-7 items-center gap-1 rounded-md px-2 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 data-open:bg-accent data-open:text-foreground",
          )}
          disabled={disabled}
          type="button"
        >
          {EXECUTION_MODES[activeIndex]?.label ?? "自动"}
          <ChevronDown className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-auto p-2">
        <div
          aria-label="切换研究模式"
          className="relative grid h-8 w-64 grid-cols-4 rounded-md bg-muted p-0.5"
          role="radiogroup"
        >
          <span
            aria-hidden
            className="absolute inset-y-0.5 left-0.5 w-[calc(25%-0.25rem)] rounded-[5px] bg-background shadow-sm transition-transform duration-200"
            style={{ transform: `translateX(${Math.max(0, activeIndex) * 100}%)` }}
          />
          {EXECUTION_MODES.map((mode) => (
            <button
              aria-checked={value === mode.value}
              className={cn(
                "relative z-10 rounded-[5px] px-1 text-xs transition-colors",
                value === mode.value ? "text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
              key={mode.value}
              onClick={() => onChange(mode.value)}
              role="radio"
              type="button"
            >
              {mode.label}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
