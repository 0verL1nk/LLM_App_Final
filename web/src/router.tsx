import { Navigate, createRootRoute, createRoute, createRouter, lazyRouteComponent, redirect } from "@tanstack/react-router"

import { AppShell } from "@/components/app-shell"
import { CreateProjectDialog } from "@/components/create-project-dialog"
import { EmptyState, PageError, PageLoading } from "@/components/page-state"
import { useProjects } from "@/lib/queries"

function WorkspaceEntry() {
  const projects = useProjects()
  if (projects.isLoading) return <PageLoading />
  if (projects.error) return <PageError error={projects.error} retry={() => void projects.refetch()} />
  const project = projects.data?.[0]
  if (project) return <Navigate to="/projects/$projectId" params={{ projectId: project.project_uid }} replace />
  return <div className="flex min-h-dvh items-center justify-center p-6"><EmptyState title="创建第一个研究项目" description="项目会承载资料、研究脉络和长期记忆。" action={<CreateProjectDialog />} /></div>
}

const rootRoute = createRootRoute({ component: AppShell })
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", beforeLoad: () => { throw redirect({ to: "/projects" }) } })
const projectsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects", component: WorkspaceEntry })
const projectRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId", component: lazyRouteComponent(() => import("@/pages/project-overview-page"), "ProjectOverviewPage") })
const libraryRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId/library", component: lazyRouteComponent(() => import("@/pages/library-page"), "LibraryPage") })
const researchRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId/research/$sessionId", component: lazyRouteComponent(() => import("@/pages/research-page"), "ResearchPage") })
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/settings", component: lazyRouteComponent(() => import("@/pages/settings-page"), "SettingsPage") })
const evalsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/evals", component: lazyRouteComponent(() => import("@/pages/evals-page"), "EvalsPage") })

const routeTree = rootRoute.addChildren([indexRoute, projectsRoute, projectRoute, libraryRoute, researchRoute, settingsRoute, evalsRoute])
export const router = createRouter({ routeTree, defaultPreload: "intent", scrollRestoration: true })

declare module "@tanstack/react-router" {
  interface Register { router: typeof router }
}
