import { Navigate, useParams } from "@tanstack/react-router"

import { PageError, PageLoading } from "@/components/page-state"
import { useSessions } from "@/lib/queries"

export function ProjectOverviewPage() {
  const { projectId } = useParams({ strict: false }) as { projectId: string }
  const sessions = useSessions(projectId)
  if (sessions.error) return <div className="mx-auto max-w-6xl px-5 py-8 lg:px-8"><PageError error={sessions.error} /></div>
  if (sessions.isLoading) return <div className="mx-auto max-w-6xl px-5 py-8 lg:px-8"><PageLoading /></div>
  const mainSession = sessions.data?.find((session) => session.is_main) ?? sessions.data?.[0]
  return mainSession ? <Navigate to="/projects/$projectId/research/$sessionId" params={{ projectId, sessionId: mainSession.session_uid }} replace /> : <PageError error={new Error("项目主研究脉络不可用")} />
}
