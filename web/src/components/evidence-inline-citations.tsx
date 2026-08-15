import { InlineCitation, InlineCitationSource } from "@/components/ai-elements/inline-citation";
import { Badge } from "@/components/ui/badge";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { ReactNode } from "react";
import { createContext } from "react";

type EvidenceRecord = Record<string, unknown>;

export const CitationContext = createContext<{ evidence: EvidenceRecord[]; onInspect: () => void }>({
  evidence: [],
  onInspect: () => {},
});

function evidenceSourceLabel(item: EvidenceRecord | undefined, label: string): string {
  if (!item) return `证据 ${label || "?"}`;
  return String(item.doc_name ?? item.doc_uid ?? `证据 ${label || "?"}`);
}

// Stable module-level identity: MessageResponse is memoized on children, so
// the citation data flows through context instead of these props.
export const evidenceMarkdownComponents = {
  a: ({ href, children }: { href?: string; children?: ReactNode }) => {
    if (!href || !href.startsWith("#evidence-")) {
      return <a href={href}>{children}</a>;
    }
    return (
      <CitationContext.Consumer>
        {({ evidence, onInspect }) => {
          const raw = Array.isArray(children) ? children.join("") : String(children ?? "");
          const label = raw.replace(/[[\]]/g, "").trim();
          const index = Number.parseInt(label, 10) - 1;
          const item = Number.isFinite(index) ? evidence[index] : undefined;
          const title = evidenceSourceLabel(item, label);
          const page = item?.page_number ?? item?.page;
          return (
            <InlineCitation>
              <HoverCard closeDelay={100} openDelay={100}>
                <HoverCardTrigger asChild>
                  <Badge
                    className="align-baseline text-xs"
                    onClick={onInspect}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") onInspect();
                    }}
                    role="button"
                    tabIndex={0}
                    variant="secondary"
                  >
                    {label || "?"}
                  </Badge>
                </HoverCardTrigger>
                <HoverCardContent className="w-72 p-3" side="top">
                  <InlineCitationSource
                    title={title}
                    description={page === undefined || page === null ? undefined : `第 ${page} 页`}
                  />
                </HoverCardContent>
              </HoverCard>
            </InlineCitation>
          );
        }}
      </CitationContext.Consumer>
    );
  },
};
