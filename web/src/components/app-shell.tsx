import {
  Link,
  Outlet,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import {
  BookOpen,
  ChevronDown,
  Menu,
  MessageSquarePlus,
  Settings,
} from "lucide-react";
import { useEffect } from "react";
import { toast } from "sonner";

import { ResearchSessionList } from "@/components/research-session-list";
import { CreateProjectDialog } from "@/components/create-project-dialog";
import { DesktopTitlebar } from "@/components/desktop-titlebar";
import { PaperSageBrand } from "@/components/papersage-logo";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { desktopWindowControls } from "@/lib/platform";
import { useCreateSession, useProjects, useSessions } from "@/lib/queries";
import { useUiStore } from "@/stores/ui-store";

const nav = [{ to: "/settings", label: "设置", icon: Settings }] as const;

function Navigation() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  return (
    <nav className="flex flex-col gap-1">
      {nav.map((item) => {
        const Icon = item.icon;
        const active = pathname.startsWith(item.to);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={cn(
              "flex h-10 items-center gap-3 rounded-md px-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              active && "bg-accent text-foreground",
            )}
          >
            <Icon className="size-4" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function WorkspaceSidebar({
  includeBrand = false,
}: {
  includeBrand?: boolean;
}) {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const navigate = useNavigate();
  const projects = useProjects();
  const routeProjectId = pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const rememberedProjectId = useUiStore((state) => state.currentProjectId);
  const projectId = routeProjectId ?? rememberedProjectId;
  const currentProject = projects.data?.find(
    (project) => project.project_uid === projectId,
  );
  const sessions = useSessions(projectId ?? "", Boolean(projectId));
  const createSession = useCreateSession(projectId ?? "");
  const selectedSessionId = pathname.match(/\/research\/([^/]+)/)?.[1] ?? "";
  const createBranch = async (): Promise<void> => {
    if (!projectId) return;
    try {
      const created = await createSession.mutateAsync("新探索");
      await navigate({
        to: "/projects/$projectId/research/$sessionId",
        params: { projectId, sessionId: created.session_uid },
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建探索失败");
    }
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {includeBrand &&
        (projectId ? (
          <Link
            to="/projects/$projectId"
            params={{ projectId }}
            className="mb-5 flex h-10 items-center rounded-lg px-2 hover:bg-muted"
          >
            <PaperSageBrand className="text-sm" />
          </Link>
        ) : (
          <div className="mb-5 flex h-10 items-center px-2">
            <PaperSageBrand className="text-sm" />
          </div>
        ))}
      <nav className="space-y-1">
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={() => void createBranch()}
          disabled={!projectId || createSession.isPending}
        >
          <MessageSquarePlus />
          新建探索
        </Button>
        {projectId && (
          <Button variant="ghost" className="w-full justify-start" asChild>
            <Link to="/projects/$projectId/library" params={{ projectId }}>
              <BookOpen />
              资料库
            </Link>
          </Button>
        )}
        <CreateProjectDialog />
      </nav>
      {currentProject && (
        <>
          <div className="mt-5 px-2 text-xs font-medium text-muted-foreground">
            当前项目
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="mt-1 w-full justify-between px-2 font-medium"
              >
                <span className="truncate">{currentProject.project_name}</span>
                <ChevronDown className="size-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-60">
              <DropdownMenuLabel>切换项目</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {projects.data?.map((project) => (
                <DropdownMenuItem
                  key={project.project_uid}
                  onSelect={() =>
                    void navigate({
                      to: "/projects/$projectId",
                      params: { projectId: project.project_uid },
                    })
                  }
                >
                  {project.project_name}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <div className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-2 flex items-center justify-between px-2">
              <span className="text-xs font-medium text-muted-foreground">
                研究脉络
              </span>
              <span className="text-xs text-muted-foreground">
                {sessions.data?.length ?? 0}
              </span>
            </div>
            <ScrollArea className="min-h-0 flex-1">
              <ResearchSessionList
                projectId={projectId!}
                selectedSessionId={selectedSessionId}
                sessions={sessions.data ?? []}
              />
            </ScrollArea>
          </div>
        </>
      )}
    </div>
  );
}

export function AppShell() {
  const { mobileNavOpen, setMobileNavOpen, setCurrentProjectId } = useUiStore();
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const desktop = Boolean(desktopWindowControls());
  const routeProjectId = pathname.match(/^\/projects\/([^/]+)/)?.[1];

  useEffect(() => {
    if (routeProjectId) setCurrentProjectId(routeProjectId);
  }, [routeProjectId, setCurrentProjectId]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("desktop-app", desktop);
    return () => root.classList.remove("desktop-app");
  }, [desktop]);

  return (
    <div
      className={cn(
        "bg-background",
        desktop ? "h-dvh overflow-hidden" : "min-h-screen",
      )}
    >
      <DesktopTitlebar />
      <aside
        className={cn(
          "fixed bottom-0 left-0 z-40 hidden w-64 border-r bg-sidebar p-3 md:flex md:flex-col",
          desktop ? "top-9" : "top-0",
        )}
      >
        <WorkspaceSidebar includeBrand={!desktop} />
        <div className="mt-auto border-t pt-3">
          <Navigation />
        </div>
      </aside>
      <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-background/90 px-4 backdrop-blur md:hidden">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileNavOpen(true)}
          aria-label="打开导航"
        >
          <Menu />
        </Button>
        <div className="ml-3">
          <PaperSageBrand />
        </div>
      </header>
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent side="left" className="flex w-72 flex-col p-3">
          <SheetHeader>
            <SheetTitle>
              <PaperSageBrand />
            </SheetTitle>
          </SheetHeader>
          <div className="mt-5 min-h-0 flex-1">
            <WorkspaceSidebar />
          </div>
          <div className="border-t pt-3">
            <Navigation />
          </div>
        </SheetContent>
      </Sheet>
      <main
        className={cn(
          "min-w-0 md:pl-64",
          desktop && "h-dvh overflow-y-auto overscroll-contain pt-9",
        )}
      >
        <Outlet />
      </main>
    </div>
  );
}
