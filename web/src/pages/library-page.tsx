import { useParams } from "@tanstack/react-router";
import {
  CheckCircle2,
  FileText,
  LoaderCircle,
  RefreshCw,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useRef } from "react";
import { toast } from "sonner";

import { ProjectHeader } from "@/components/project-header";
import { EmptyState, PageError, PageLoading } from "@/components/page-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  useDocuments,
  useRetryDocument,
  useSessions,
  useUploadDocuments,
} from "@/lib/queries";

const stageLabels: Record<string, string> = {
  queued: "等待处理",
  extracting: "提取文本",
  ocr: "OCR 识别",
  loading_model: "加载模型",
  chunking: "文档切分",
  embedding: "生成向量",
  publishing: "发布索引",
  ready: "可检索",
  failed: "失败",
};

function IngestionProgress({
  stage,
  current,
  total,
}: {
  stage: string;
  current: number;
  total: number;
}) {
  if (total > 0)
    return (
      <>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <LoaderCircle className="size-3 animate-spin" />
            {stageLabels[stage] ?? stage}
          </span>
          <span>
            {current}/{total}
          </span>
        </div>
        <Progress value={(current / total) * 100} />
      </>
    );
  return (
    <>
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <LoaderCircle className="size-3 animate-spin" />
        {stageLabels[stage] ?? stage}
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-muted">
        <div className="h-full w-1/3 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-primary" />
      </div>
    </>
  );
}

export function LibraryPage() {
  const { projectId } = useParams({ strict: false }) as { projectId: string };
  const docs = useDocuments(projectId);
  const sessions = useSessions(projectId);
  const upload = useUploadDocuments(projectId);
  const retry = useRetryDocument(projectId);
  const input = useRef<HTMLInputElement>(null);
  const selectFiles = async (fileList: FileList | null) => {
    const files = Array.from(fileList ?? []);
    if (!files.length) return;
    const result = await upload.mutateAsync(files);
    if (result.uploaded.length) {
      toast.success(
        `已上传 ${result.uploaded.length} 份文档，后台开始并行解析`,
      );
    }
    if (result.failed.length) {
      const details = result.failed
        .slice(0, 2)
        .map((item) => `${item.fileName}：${item.message}`)
        .join("；");
      const remainder =
        result.failed.length > 2
          ? `；另有 ${result.failed.length - 2} 份失败`
          : "";
      toast.error(
        `${result.failed.length} 份文档上传失败：${details}${remainder}`,
      );
    }
    if (input.current) input.current.value = "";
  };
  return (
    <>
      <ProjectHeader
        projectId={projectId}
        researchSessionId={sessions.data?.[0]?.session_uid}
      />
      <div className="mx-auto max-w-6xl px-5 py-8 lg:px-8">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold">资料库</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              可一次选择多份文档；上传后异步解析，已发布版本会自动进入后续检索。
            </p>
          </div>
          <>
            <input
              ref={input}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff"
              className="hidden"
              onChange={(event) => void selectFiles(event.target.files)}
            />
            <Button
              onClick={() => input.current?.click()}
              disabled={upload.isPending}
            >
              <UploadCloud />
              {upload.isPending
                ? `正在上传 ${upload.variables?.length ?? 0} 份…`
                : "上传文档"}
            </Button>
          </>
        </header>
        {docs.isLoading ? (
          <PageLoading />
        ) : docs.error ? (
          <PageError error={docs.error} retry={() => void docs.refetch()} />
        ) : !docs.data?.length ? (
          <EmptyState
            title="资料库为空"
            description="支持 PDF、Word 和纯文本。上传后可以立即创建会话，无需等待解析。"
            action={
              <Button onClick={() => input.current?.click()}>
                <UploadCloud />
                选择文档
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {docs.data.map((doc) => {
              const state = doc.ingestion?.status ?? "queued";
              const current = doc.ingestion?.current_items ?? 0;
              const total = doc.ingestion?.total_items ?? 0;
              return (
                <Card key={doc.uid}>
                  <CardContent className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_220px_auto] md:items-center">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="rounded-md bg-muted p-2.5">
                        <FileText className="size-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {doc.file_name}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {doc.created_at || "刚刚"}
                        </p>
                      </div>
                    </div>
                    <div>
                      {state === "ready" ? (
                        <Badge variant="outline" className="text-emerald-500">
                          <CheckCircle2 />
                          可检索
                        </Badge>
                      ) : state === "failed" ? (
                        <div>
                          <Badge variant="destructive">
                            <XCircle />
                            解析失败
                          </Badge>
                          <p className="mt-1 line-clamp-1 text-xs text-destructive">
                            {doc.ingestion?.error_message}
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <IngestionProgress
                            stage={doc.ingestion?.stage ?? state}
                            current={current}
                            total={total}
                          />
                        </div>
                      )}
                    </div>
                    {state === "failed" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => retry.mutate(doc.uid)}
                        disabled={retry.isPending}
                      >
                        <RefreshCw />
                        重试
                      </Button>
                    ) : (
                      <span />
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
