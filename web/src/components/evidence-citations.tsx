import { ArrowUpRight } from "lucide-react";

type Evidence = Record<string, unknown>;

function sourceLabel(evidence: Evidence, index: number): string {
  return String(evidence.doc_name ?? evidence.doc_uid ?? `证据 ${index + 1}`);
}

function sourceLocation(evidence: Evidence): string | null {
  const page = evidence.page_number ?? evidence.page;
  return page === undefined || page === null ? null : `第 ${page} 页`;
}

export function EvidenceCitations({
  evidence,
  onInspect,
}: {
  evidence: Evidence[];
  onInspect: () => void;
}) {
  if (!evidence.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2 border-t pt-3" aria-label="引用证据">
      {evidence.map((item, index) => (
        <button
          className="inline-flex max-w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          key={String(item.chunk_id ?? index)}
          onClick={onInspect}
          type="button"
        >
          <span className="inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-secondary font-medium text-foreground">
            {index + 1}
          </span>
          <span className="max-w-48 truncate font-medium text-foreground">{sourceLabel(item, index)}</span>
          {sourceLocation(item) && <span className="shrink-0">· {sourceLocation(item)}</span>}
          <ArrowUpRight className="size-3 shrink-0" aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
