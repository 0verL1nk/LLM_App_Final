"use client";

import { cn } from "@/lib/utils";

function Loader({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      className={cn("flex items-center gap-1.5", className)}
      role="status"
      aria-label="加载中"
      {...props}
    >
      <span className="size-1.5 animate-pulse rounded-full bg-foreground/50" />
      <span className="size-1.5 animate-pulse rounded-full bg-foreground/50 [animation-delay:150ms]" />
      <span className="size-1.5 animate-pulse rounded-full bg-foreground/50 [animation-delay:300ms]" />
    </span>
  );
}

export { Loader };
