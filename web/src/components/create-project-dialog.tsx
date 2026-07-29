import { zodResolver } from "@hookform/resolvers/zod"
import { useNavigate } from "@tanstack/react-router"
import { FolderPlus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useCreateProject } from "@/lib/queries"

const projectFormSchema = z.object({
  project_name: z.string().trim().min(1, "请输入项目名称").max(120),
  description: z.string().trim().max(1000),
})

type ProjectForm = z.infer<typeof projectFormSchema>

export function CreateProjectDialog() {
  const [open, setOpen] = useState(false)
  const create = useCreateProject()
  const navigate = useNavigate()
  const form = useForm<ProjectForm>({ resolver: zodResolver(projectFormSchema), defaultValues: { project_name: "", description: "" } })
  const submit = form.handleSubmit(async (values) => {
    try {
      const project = await create.mutateAsync(values)
      setOpen(false)
      form.reset()
      await navigate({ to: "/projects/$projectId", params: { projectId: project.project_uid } })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建失败")
    }
  })
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="ghost" className="w-full justify-start"><FolderPlus />新建项目</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>创建研究项目</DialogTitle><DialogDescription>项目统一承载资料、研究脉络和长期记忆。</DialogDescription></DialogHeader><form id="create-project" onSubmit={submit} className="space-y-4"><div className="space-y-2"><Label htmlFor="project-name">名称</Label><Input id="project-name" autoFocus {...form.register("project_name")} />{form.formState.errors.project_name && <p className="text-xs text-destructive">{form.formState.errors.project_name.message}</p>}</div><div className="space-y-2"><Label htmlFor="project-description">研究目标</Label><Textarea id="project-description" rows={4} placeholder="这项研究要回答什么问题？" {...form.register("description")} /></div></form><DialogFooter><Button type="submit" form="create-project" disabled={create.isPending}>{create.isPending ? "创建中…" : "创建项目"}</Button></DialogFooter></DialogContent></Dialog>
}
