import { Link, useRouterState } from "@tanstack/react-router"
import { BookOpen, MessageSquareText } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useProject } from "@/lib/queries"

export function ProjectHeader({ projectId, researchSessionId }: { projectId: string; researchSessionId?: string }) {
  const project = useProject(projectId)
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const inLibrary = pathname.endsWith("/library")
  const inResearch = pathname.includes("/research/")

  return <header className="border-b bg-background"><div className="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-4 py-3 lg:px-8"><div className="min-w-0">{project.isLoading ? <Skeleton className="h-5 w-48" /> : <><h1 className="truncate text-sm font-semibold">{project.data?.project_name}</h1><p className="truncate text-xs text-muted-foreground">{project.data?.description || "研究项目"}</p></>}</div><div className="flex shrink-0 items-center gap-2">{!inLibrary && <Button variant="outline" size="sm" asChild><Link to="/projects/$projectId/library" params={{ projectId }}><BookOpen />资料</Link></Button>}{researchSessionId && !inResearch && <Button size="sm" asChild><Link to="/projects/$projectId/research/$sessionId" params={{ projectId, sessionId: researchSessionId }}><MessageSquareText />继续研究</Link></Button>}</div></div></header>
}
