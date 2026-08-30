import { MindmapTree } from "@/components/a2ui-mindmap";
import { parseResearchMap } from "@/lib/research-map";

/**
 * Render one streamed component part. The backend stores the fragment
 * verbatim; parsing and presentation limits live here, client side.
 */
export function ComponentPart({
  component,
  state,
  xml,
  error,
  onInspectEvidence,
}: {
  component: string;
  state: string;
  xml?: string;
  error?: string;
  onInspectEvidence?: () => void;
}) {
  if (component !== "research-map") {
    return (
      <p className="my-2 text-xs text-muted-foreground">
        这条回复包含暂不支持的可视化组件（{component}），正文仍然可用。
      </p>
    );
  }
  if (state === "streaming") {
    return (
      <div className="my-3 h-20 animate-pulse rounded-xl border bg-background/60" aria-label="正在生成可视化梳理" />
    );
  }
  if (state === "error") {
    return (
      <p className="my-2 text-xs text-muted-foreground">
        这张思维导图{error ? `生成时未通过校验（${error}）` : "生成时未完成"}；正文中的文字版仍然可用。
      </p>
    );
  }
  const parsed = parseResearchMap(xml ?? "");
  if (!parsed) {
    return (
      <p className="my-2 text-xs text-muted-foreground">
        这条回复包含一张思维导图，但内容格式无法解析；正文中的文字版仍然可用。
      </p>
    );
  }
  return <MindmapTree title={parsed.title} root={parsed.root} onInspectEvidence={onInspectEvidence} />;
}
