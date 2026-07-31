import { Link } from "@tanstack/react-router"

import type { Session } from "@/lib/schemas"
import { cn } from "@/lib/utils"

interface ResearchSessionListProps {
  projectId: string
  selectedSessionId: string
  sessions: Session[]
  onSelect?: () => void
}

export function ResearchSessionList({ projectId, selectedSessionId, sessions, onSelect }: ResearchSessionListProps) {
  const mainSession = sessions.find((session) => session.is_main) ?? sessions[0]
  const branches = sessions.filter((session) => session.session_uid !== mainSession?.session_uid)
  const sessionLink = (session: Session) => <Link key={session.session_uid} to="/projects/$projectId/research/$sessionId" params={{ projectId, sessionId: session.session_uid }} onClick={onSelect} aria-current={session.session_uid === selectedSessionId ? "page" : undefined} className={cn("block min-w-0 rounded-md px-3 py-2.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground", session.session_uid === selectedSessionId && "bg-accent text-foreground")}><p title={session.session_name} className="truncate font-medium">{session.session_name}</p><p className="mt-1 truncate text-xs text-muted-foreground">{session.message_count} 条消息</p></Link>
  return <div className="space-y-4 pb-4">{mainSession && <section><p className="px-3 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground">主研究脉络</p>{sessionLink(mainSession)}</section>}{branches.length > 0 && <section><p className="px-3 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground">探索分支</p><div className="space-y-1">{branches.map(sessionLink)}</div></section>}</div>
}
