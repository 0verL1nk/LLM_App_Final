import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ArrowLeft, CheckCircle2, Database, Download, LockKeyhole, Save, ServerCog } from "lucide-react"
import { useEffect, useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { PaperSageBrand } from "@/components/papersage-logo"
import { PageError, PageLoading } from "@/components/page-state"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api } from "@/lib/api"
import { desktopWindowControls } from "@/lib/platform"
import { keys, useSettings } from "@/lib/queries"
import { settingsSchema } from "@/lib/schemas"
import { useUiStore } from "@/stores/ui-store"

const formSchema = z.object({
  api_key: z.string(),
  model_name: z.string().trim().min(1, "请输入模型名称"),
  base_url: z.string().trim().refine((value) => !value || z.url().safeParse(value).success, "请输入有效 URL"),
  rag_index_batch_size: z.number().int().min(1).max(4096),
  local_rag_project_max_chars: z.number().int().min(0),
  local_rag_project_max_chunks: z.number().int().min(0),
})
type SettingsForm = z.infer<typeof formSchema>

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null
}

function DesktopUpdatesCard() {
  const desktop = desktopWindowControls()
  const [checking, setChecking] = useState(false)
  if (!desktop) return null
  const checkForUpdates = async (): Promise<void> => {
    setChecking(true)
    try {
      const result = await desktop.checkForUpdates()
      if (result.supported) toast.message("正在检查更新", { description: "如有新版本，系统会询问是否下载。" })
      else toast.message("此安装方式由系统包管理器更新")
    } catch (error) {
      toast.error("无法检查更新", { description: error instanceof Error ? error.message : "请稍后重试。" })
    } finally {
      setChecking(false)
    }
  }
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Download className="size-4 text-primary" />桌面更新</CardTitle><CardDescription>通过 PaperSage 的 GitHub Release 检查更新。发现新版本后，由你确认下载和重启安装。</CardDescription></CardHeader><CardContent><Button type="button" variant="outline" onClick={() => void checkForUpdates()} disabled={checking}><Download />{checking ? "检查中…" : "检查更新"}</Button></CardContent></Card>
}

export function SettingsPage() {
  const currentProjectId = useUiStore((state) => state.currentProjectId)
  const query = useSettings()
  const client = useQueryClient()
  const form = useForm<SettingsForm>({
    resolver: zodResolver(formSchema),
    defaultValues: { api_key: "", model_name: "", base_url: "", rag_index_batch_size: 256, local_rag_project_max_chars: 0, local_rag_project_max_chunks: 0 },
  })

  useEffect(() => {
    if (!query.data) return
    form.reset({
      api_key: "",
      model_name: query.data.model_name,
      base_url: query.data.base_url,
      rag_index_batch_size: query.data.rag_index_batch_size ?? 256,
      local_rag_project_max_chars: query.data.local_rag_project_max_chars ?? 0,
      local_rag_project_max_chunks: query.data.local_rag_project_max_chunks ?? 0,
    })
  }, [form, query.data])

  const save = useMutation({
    mutationFn: (values: SettingsForm) => api("/settings", settingsSchema, { method: "PUT", body: JSON.stringify({ ...values, api_key: values.api_key || null }) }),
    onSuccess: (data) => {
      client.setQueryData(keys.settings, data)
      form.reset({ ...form.getValues(), api_key: "" })
      toast.success("设置已保存", { description: "新的配置将用于后续研究和资料处理。" })
    },
    onError: (error) => toast.error("保存失败", { description: error.message }),
  })

  if (query.isLoading) return <div className="mx-auto max-w-3xl px-5 py-10"><PageLoading /></div>
  if (query.error) return <div className="mx-auto max-w-3xl px-5 py-10"><PageError error={query.error} /></div>

  const configured = query.data?.api_key_configured
  return <div className="mx-auto w-full max-w-3xl px-5 py-10 lg:px-8">
    <header className="mb-9 space-y-3">
      <div className="flex items-center justify-between gap-4"><PaperSageBrand className="text-sm text-muted-foreground" />{currentProjectId && <Button variant="ghost" size="sm" asChild><Link to="/projects/$projectId" params={{ projectId: currentProjectId }}><ArrowLeft />返回项目</Link></Button>}</div>
      <div><h1 className="text-3xl font-semibold tracking-tight">设置</h1><p className="mt-2 text-sm leading-6 text-muted-foreground">配置用于研究和资料库的模型连接。密钥只保存于服务端，已保存的值不会回传到浏览器。</p></div>
    </header>

    <form onSubmit={form.handleSubmit((values) => save.mutate(values))} className="space-y-6 pb-24">
      <Card className="overflow-hidden">
        <CardHeader className="border-b bg-muted/20">
          <div className="flex items-start justify-between gap-4"><div><CardTitle className="flex items-center gap-2"><ServerCog className="size-4 text-primary" />模型连接</CardTitle><CardDescription className="mt-1.5">使用兼容 OpenAI API 的服务及模型。</CardDescription></div><Badge variant={configured ? "secondary" : "outline"} className="shrink-0 gap-1.5">{configured && <CheckCircle2 className="size-3" />}{configured ? "已配置" : "待配置"}</Badge></div>
        </CardHeader>
        <CardContent className="grid gap-6 pt-6 md:grid-cols-2">
          <div className="space-y-2 md:col-span-2"><div className="flex items-center justify-between gap-3"><Label htmlFor="api-key">API Key</Label>{configured && <span className="text-xs text-muted-foreground">当前：{query.data?.api_key_hint}</span>}</div><Input id="api-key" type="password" autoComplete="new-password" placeholder={configured ? "留空则保留当前密钥" : "输入 API Key"} {...form.register("api_key")} /><p className="flex items-center gap-1.5 text-xs leading-5 text-muted-foreground"><LockKeyhole className="size-3.5" />仅在你保存时发送；留空不会清除已有密钥。</p></div>
          <div className="space-y-2"><Label htmlFor="model-name">模型名称</Label><Input id="model-name" placeholder="qwen-plus" {...form.register("model_name")} /><FieldError message={form.formState.errors.model_name?.message} /></div>
          <div className="space-y-2"><Label htmlFor="base-url">服务地址</Label><Input id="base-url" placeholder="https://api.example.com/v1" {...form.register("base_url")} /><FieldError message={form.formState.errors.base_url?.message} /></div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Database className="size-4 text-primary" />资料库索引</CardTitle><CardDescription>控制文档写入向量索引时的批量大小和完整性。建议保留完整索引。</CardDescription></CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-3">
          <div className="space-y-2"><Label htmlFor="batch">每批向量数</Label><Input id="batch" type="number" min="1" max="4096" {...form.register("rag_index_batch_size", { valueAsNumber: true })} /><p className="text-xs leading-5 text-muted-foreground">较小更稳，较大通常更快。</p><FieldError message={form.formState.errors.rag_index_batch_size?.message} /></div>
          <div className="space-y-2"><Label htmlFor="max-chars">单项目字符上限</Label><Input id="max-chars" type="number" min="0" {...form.register("local_rag_project_max_chars", { valueAsNumber: true })} /><p className="text-xs leading-5 text-muted-foreground">0 为不截断，索引全部文本。</p><FieldError message={form.formState.errors.local_rag_project_max_chars?.message} /></div>
          <div className="space-y-2"><Label htmlFor="max-chunks">单项目分块上限</Label><Input id="max-chunks" type="number" min="0" {...form.register("local_rag_project_max_chunks", { valueAsNumber: true })} /><p className="text-xs leading-5 text-muted-foreground">0 为不限制分块数量。</p><FieldError message={form.formState.errors.local_rag_project_max_chunks?.message} /></div>
        </CardContent>
      </Card>

      <DesktopUpdatesCard />

      <div className="sticky bottom-0 z-20 -mx-5 border-t bg-background/95 px-5 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 lg:-mx-8 lg:px-8"><div className="mx-auto flex max-w-3xl items-center justify-between gap-4"><p className="hidden text-xs text-muted-foreground sm:block">配置变更不会中断已经开始的研究。</p><Button type="submit" className="ml-auto" disabled={save.isPending || !form.formState.isDirty}><Save className="size-4" />{save.isPending ? "保存中…" : "保存设置"}</Button></div></div>
    </form>
  </div>
}
