import { Network } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { surfaceFromPersisted } from "@/lib/a2ui"
import type { MindmapNode } from "@/lib/a2ui"

function Node({ node, depth = 0 }: { node: MindmapNode; depth?: number }) {
  return <li className="relative pl-5 before:absolute before:top-0 before:left-0 before:h-5 before:w-4 before:rounded-bl-md before:border-b before:border-l before:border-border"><span className={depth === 0 ? "inline-flex rounded-lg bg-foreground px-3 py-1.5 font-medium text-background" : "inline-flex rounded-md border bg-background px-2.5 py-1.5 text-sm"}>{node.label}</span>{node.children.length > 0 && <ul className="mt-3 space-y-3">{node.children.map((child, index) => <Node key={`${child.label}-${index}`} node={child} depth={depth + 1} />)}</ul>}</li>
}

export function A2UIMindmap({ surface }: { surface: Record<string, unknown> | null | undefined }) {
  const root = surfaceFromPersisted(surface)?.mindmap
  if (!root) return null
  return <Card className="mt-4 overflow-hidden border-border/80 shadow-none"><CardHeader className="flex-row items-center gap-2 border-b bg-muted/30 py-3"><Network className="size-4 text-muted-foreground" /><CardTitle className="text-sm">知识结构</CardTitle></CardHeader><CardContent className="overflow-x-auto p-5"><ul className="min-w-max space-y-3"><Node node={root} /></ul></CardContent></Card>
}
