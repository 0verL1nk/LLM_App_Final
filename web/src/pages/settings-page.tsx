import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ArrowLeft, CheckCircle2, Database, Download, FileWarning, FolderOpen, Gauge, LockKeyhole, RotateCw, Save, ServerCog } from "lucide-react"
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
import { Progress } from "@/components/ui/progress"
import { api } from "@/lib/api"
import { desktopWindowControls } from "@/lib/platform"
import { keys, useDocumentConversion, useSettings } from "@/lib/queries"
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
  const desktopUpdate = useUiStore((state) => state.desktopUpdate)
  const version = useUiStore((state) => state.desktopVersion)
  const [checking, setChecking] = useState(false)
  const [installing, setInstalling] = useState(false)
  if (!desktop) return null
  const installUpdate = async (): Promise<void> => {
    setInstalling(true)
    try {
      await desktop.installUpdate()
    } catch {
      toast.error("无法启动更新安装", { description: "请稍后重试，或下次退出应用时自动安装。" })
    } finally {
      setInstalling(false)
    }
  }
  const checkForUpdates = async (): Promise<void> => {
    setChecking(true)
    try {
      const result = await desktop.checkForUpdates()
      if (result.status === "available") toast.success(`发现新版本 ${result.version ?? ""}`.trim(), { description: "已在后台开始下载。" })
      else if (result.status === "up-to-date") toast.success("已是最新版本", { description: "暂时不需要更新。" })
      else if (result.status === "unsupported") {
        const description = result.reason === "development"
          ? "当前是开发或便携运行方式，未接入发布更新。请使用 PaperSage 桌面安装包。"
          : result.reason === "system-managed"
            ? "当前 Linux 安装由系统包管理器负责更新。"
            : "当前安装方式没有可用的自动更新通道。请从原安装来源更新。"
        toast.message("无法通过应用内更新", { description })
      }
      else toast.error("暂时无法检查更新", { description: "请确认网络连接后再试一次。" })
    } catch {
      toast.error("暂时无法检查更新", { description: "请稍后再试一次。" })
    } finally {
      setChecking(false)
    }
  }
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Download className="size-4 text-primary" />应用更新</CardTitle><CardDescription>{version ? `当前版本 v${version}。` : ""}发现新版本后会在后台下载，可立即重启安装，或在下次退出应用时自动安装。</CardDescription></CardHeader><CardContent className="space-y-4"><Button type="button" variant="outline" onClick={() => void checkForUpdates()} disabled={checking || desktopUpdate.phase === "downloading"}><Download />{checking ? "正在检查…" : desktopUpdate.phase === "downloading" ? "正在下载" : "检查新版本"}</Button>{desktopUpdate.phase === "downloading" && <div className="space-y-2 rounded-lg border border-border/70 bg-muted/30 p-3"><div className="flex items-center justify-between text-sm"><span>正在下载 {desktopUpdate.version ? `v${desktopUpdate.version}` : "更新"}</span><span className="tabular-nums text-muted-foreground">{Math.round(desktopUpdate.percent ?? 0)}%</span></div><Progress value={desktopUpdate.percent ?? 0} /><p className="text-xs text-muted-foreground">下载期间可以继续使用 PaperSage。</p></div>}{desktopUpdate.phase === "ready" && <div className="space-y-3 rounded-lg border border-border/70 bg-muted/30 p-3"><p className="text-sm text-emerald-600 dark:text-emerald-400">新版本已下载完成，重启 PaperSage 即可完成安装。</p><Button type="button" onClick={() => void installUpdate()} disabled={installing}><RotateCw />{installing ? "正在重启…" : "重启并更新"}</Button></div>}{desktopUpdate.phase === "failed" && <p className="text-sm text-destructive">下载未完成，请检查网络后重试。</p>}</CardContent></Card>
}

function DesktopDiagnosticsCard() {
  const desktop = desktopWindowControls()
  if (!desktop) return null
  const openLogs = async (): Promise<void> => {
    const error = await desktop.openLogs()
    if (error) toast.error("无法打开日志文件夹", { description: error })
  }
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileWarning className="size-4 text-primary" />诊断日志</CardTitle><CardDescription>异常发生后，可在这里打开日志文件夹。日志可能包含操作和文档处理的技术信息，请勿公开分享。</CardDescription></CardHeader><CardContent><Button type="button" variant="outline" onClick={() => void openLogs()}><FolderOpen />打开日志文件夹</Button></CardContent></Card>
}

function DocumentPreviewCard() {
  const capability = useDocumentConversion()
  const ready = capability.data?.office_preview_ready
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileWarning className="size-4 text-primary" />Office 文件预览</CardTitle><CardDescription>{ready ? "此设备已具备 Office 文件转 PDF 与定位所需的本地转换器。" : "PDF、图片与 TXT 可直接预览；DOCX、PPTX、XLSX 需要本地转换器。"}</CardDescription></CardHeader><CardContent className="flex flex-wrap items-center gap-2"><Badge variant={ready ? "secondary" : "outline"}>{ready ? "已就绪" : "需要安装"}</Badge>{capability.data?.microsoft_office && <Badge variant="outline">Microsoft Office</Badge>}{capability.data?.libreoffice && <Badge variant="outline">LibreOffice</Badge>}{!ready && <p className="w-full text-xs leading-5 text-muted-foreground">安装 Microsoft 365/Office 桌面版或 LibreOffice 后，重新打开此页即可自动检测；文件和资料库内容不会丢失。</p>}</CardContent></Card>
}

function OcrAccelerationCard() {
  const capability = useDocumentConversion()
  const ocr = capability.data?.ocr
  const gpu = ocr?.gpu_enabled === true
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Gauge className="size-4 text-primary" />本地识别加速</CardTitle><CardDescription>{gpu ? "文档识别正在使用 NVIDIA GPU 加速。" : "文档识别当前使用 CPU；GPU 加速需要 GPU 版安装包。"}</CardDescription></CardHeader><CardContent className="flex flex-wrap items-center gap-2"><Badge variant={gpu ? "secondary" : "outline"}>{gpu ? "GPU 已启用" : "CPU 模式"}</Badge>{ocr && <Badge variant="outline">{ocr.device.startsWith("gpu") ? `NVIDIA ${ocr.device}` : ocr.profile}</Badge>}</CardContent></Card>
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
      <DesktopDiagnosticsCard />
      <DocumentPreviewCard />
      <OcrAccelerationCard />

      <div className="sticky bottom-0 z-20 -mx-5 border-t bg-background/95 px-5 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 lg:-mx-8 lg:px-8"><div className="mx-auto flex max-w-3xl items-center justify-between gap-4"><p className="hidden text-xs text-muted-foreground sm:block">配置变更不会中断已经开始的研究。</p><Button type="submit" className="ml-auto" disabled={save.isPending || !form.formState.isDirty}><Save className="size-4" />{save.isPending ? "保存中…" : "保存设置"}</Button></div></div>
    </form>
  </div>
}
