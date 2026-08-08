import type { SVGProps } from "react"

import { cn } from "@/lib/utils"

type PaperSageLogoProps = SVGProps<SVGSVGElement> & {
  title?: string
}

/** The PaperSage mark: a source document connected to evidence. */
export function PaperSageLogo({ className, title = "PaperSage", ...props }: PaperSageLogoProps) {
  return (
    <svg
      aria-label={title}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      className={cn("shrink-0", className)}
      {...props}
    >
      <path
        d="M8 5.75h8.9L23.5 12v14.25H8V5.75Z"
        className="fill-primary/12 stroke-primary"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M16.9 5.75V12h6.6" className="stroke-primary" strokeWidth="2" strokeLinejoin="round" />
      <path
        d="m11 20.9 4.5-4.25 4.9 2.75"
        className="stroke-primary"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="11" cy="20.9" r="1.6" className="fill-primary" />
      <circle cx="15.5" cy="16.65" r="1.6" className="fill-primary/70" />
      <circle cx="20.4" cy="19.4" r="1.6" className="fill-primary/40" />
    </svg>
  )
}

export function PaperSageBrand({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2 font-semibold tracking-[-0.02em]", className)}>
      <PaperSageLogo className="size-6" />
      <span>PaperSage</span>
    </span>
  )
}
