import { LoaderCircle, MapPin } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

type Location = { page_no?: unknown; polygon?: unknown };

function polygonPoints(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value
    .map((point) =>
      Array.isArray(point) ? `${Number(point[0])},${Number(point[1])}` : "",
    )
    .filter(Boolean)
    .join(" ");
}

export function EvidencePreview({
  projectId,
  evidence,
}: {
  projectId: string;
  evidence: Record<string, unknown>;
}) {
  const locations = useMemo(
    () =>
      Array.isArray(evidence.ocr_locations)
        ? (evidence.ocr_locations as Location[])
        : [],
    [evidence.ocr_locations],
  );
  const pages = useMemo(
    () => [
      ...new Set(
        locations
          .map((item) => item.page_no)
          .filter((page): page is number => typeof page === "number"),
      ),
    ],
    [locations],
  );
  const initialPage = pages[0] ?? evidence.page_no;
  const [open, setOpen] = useState(false);
  const [pageNo, setPageNo] = useState<number | null>(
    typeof initialPage === "number" ? initialPage : null,
  );
  const [imageUrl, setImageUrl] = useState("");
  const [loadedPage, setLoadedPage] = useState<number | null>(null);
  const [failedPage, setFailedPage] = useState<number | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!open || typeof pageNo !== "number") return;
    let objectUrl = "";
    void fetch(
      `/api/v1/projects/${projectId}/documents/${String(evidence.doc_uid ?? "")}/preview/${pageNo}`,
      { headers: { "X-User-Id": "local-user" } },
    )
      .then((response) => (response.ok ? response.blob() : Promise.reject()))
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
        setLoadedPage(pageNo);
      })
      .catch(() => setFailedPage(pageNo));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [evidence.doc_uid, open, pageNo, projectId]);
  if (pageNo === null) return null;
  const imageReady = imageUrl && loadedPage === pageNo;
  const loadFailed = failedPage === pageNo;
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen)
          setPageNo(typeof initialPage === "number" ? initialPage : null);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <MapPin />
          定位原文
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92dvh] max-w-5xl overflow-auto">
        <DialogHeader>
          <DialogTitle>
            {String(evidence.doc_name ?? "文档")} · 第 {pageNo} 页
          </DialogTitle>
        </DialogHeader>
        {pages.length > 1 && (
          <div className="flex flex-wrap gap-2" aria-label="证据所在页面">
            {pages.map((page) => (
              <Button
                key={page}
                variant={page === pageNo ? "default" : "outline"}
                size="sm"
                onClick={() => setPageNo(page)}
              >
                第 {page} 页
              </Button>
            ))}
          </div>
        )}
        {imageReady ? (
          <div className="relative mx-auto w-fit">
            <img
              src={imageUrl}
              alt="文档页面预览"
              className="max-h-[75dvh] max-w-full"
              onLoad={(event) =>
                setSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
            />
            {size.width > 0 && (
              <svg
                className="pointer-events-none absolute inset-0 size-full"
                viewBox={`0 0 ${size.width} ${size.height}`}
              >
                {locations
                  .filter((item) => item.page_no === pageNo)
                  .map((item, index) => (
                    <polygon
                      key={index}
                      points={polygonPoints(item.polygon)}
                      fill="hsl(var(--primary) / 0.18)"
                      stroke="hsl(var(--primary))"
                      strokeWidth="3"
                    />
                  ))}
              </svg>
            )}
          </div>
        ) : loadFailed ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            页面预览尚未生成。请在资料库重新解析该文档。
          </p>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center gap-3 py-12 text-center text-sm text-muted-foreground">
            <LoaderCircle className="size-5 animate-spin" />
            正在加载原文页面…
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
