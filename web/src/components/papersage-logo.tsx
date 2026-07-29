import type { SVGProps } from "react"

import { cn } from "@/lib/utils"

type PaperSageLogoProps = SVGProps<SVGSVGElement> & {
  title?: string
}

/** The PaperSage mark: an open document turning into a connected insight. */
export function PaperSageLogo({ className, title = "PaperSage", ...props }: PaperSageLogoProps) {
  return <svg aria-label={title} viewBox="0 0 32 32" fill="none" role="img" className={cn("shrink-0", className)} {...props}>
    <path d="M5.5 8.25c3.55-1.5 6.66-1.03 9.5 1.25v14.1c-2.84-2.28-5.95-2.75-9.5-1.25V8.25Z" className="fill-primary/15 stroke-primary" strokeWidth="1.9" strokeLinejoin="round" />
    <path d="M26.5 8.25c-3.55-1.5-6.66-1.03-9.5 1.25v14.1c2.84-2.28 5.95-2.75 9.5-1.25V8.25Z" className="fill-primary/30 stroke-primary" strokeWidth="1.9" strokeLinejoin="round" />
    <path d="M16 9.5v14.1" className="stroke-primary" strokeWidth="1.9" strokeLinecap="round" />
    <circle cx="24.5" cy="6.5" r="2.25" className="fill-background stroke-primary" strokeWidth="1.7" />
    <path d="M22.85 8.02 19.8 10.2M23.42 4.9l-1.05-1.22" className="stroke-primary" strokeWidth="1.7" strokeLinecap="round" />
  </svg>
}

export function PaperSageBrand({ className }: { className?: string }) {
  return <span className={cn("flex items-center gap-2 font-semibold tracking-[-0.02em]", className)}><PaperSageLogo className="size-6" /><span>PaperSage</span></span>
}
