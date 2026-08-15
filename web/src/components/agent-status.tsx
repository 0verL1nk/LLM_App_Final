import { Loader } from "@/components/ai-elements/loader";
import { cn } from "@/lib/utils";

export function ThinkingState({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex bg-[linear-gradient(110deg,currentColor_20%,color-mix(in_oklch,currentColor_45%,transparent)_45%,currentColor_70%)] bg-[length:200%_100%] bg-clip-text text-sm text-transparent motion-safe:animate-[shimmer_1.8s_linear_infinite]",
        className,
      )}
    >
      正在思考
    </span>
  );
}

export function ResearchOrbs() {
  return (
    <div className="flex h-6 items-center gap-2" aria-label="研究任务正在启动" role="status">
      <Loader />
      <ThinkingState />
    </div>
  );
}
