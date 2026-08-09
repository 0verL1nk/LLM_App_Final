import { Link2, Network } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { surfaceFromPersisted } from "@/lib/a2ui"
import type { MindmapNode } from "@/lib/a2ui"

function Node({ node, depth = 0, onInspectEvidence }: { node: MindmapNode; depth?: number; onInspectEvidence?: () => void }) {
  const label = node.citationIds.length > 0 && onInspectEvidence
    ? <button type="button" className="inline-flex items-center gap-1.5 text-left" onClick={onInspectEvidence}>{node.label}<Link2 className="size-3 opacity-65" /><span className="sr-only">查看相关证据</span></button>
    : node.label
  return <li className="relative pl-5 before:absolute before:top-0 before:left-0 before:h-5 before:w-4 before:rounded-bl-md before:border-b before:border-l before:border-border"><span className={depth === 0 ? "inline-flex rounded-lg bg-foreground px-3 py-1.5 font-medium text-background" : "inline-flex rounded-md border bg-background px-2.5 py-1.5 text-sm"}>{label}</span>{node.children.length > 0 && <ul className="mt-3 space-y-3">{node.children.map((child, index) => <Node key={`${child.label}-${index}`} node={child} depth={depth + 1} onInspectEvidence={onInspectEvidence} />)}</ul>}</li>
}

export function A2UIMindmap({ surface, onInspectEvidence }: { surface: Record<string, unknown> | null | undefined; onInspectEvidence?: () => void }) {
  const parsed = surfaceFromPersisted(surface)
  const root = parsed?.mindmap
  if (!root) return null
  return <Card className="mt-4 overflow-hidden border-border/80 shadow-none"><CardHeader className="flex-row items-center gap-2 border-b bg-muted/30 py-3"><Network className="size-4 text-muted-foreground" /><CardTitle className="text-sm">{parsed?.title || "知识结构"}</CardTitle></CardHeader><CardContent className="overflow-x-auto p-5"><ul className="min-w-max space-y-3"><Node node={root} onInspectEvidence={onInspectEvidence} /></ul></CardContent></Card>
}
