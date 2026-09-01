import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useEvalRun, useEvalRuns, useExportFeedbackCase, useFeedbackFindings, useStartEvalRun } from "@/lib/queries"
import type { EvalCaseProgress, FeedbackCaseDraft } from "@/lib/schemas"

const STATUS_LABELS: Record<EvalCaseProgress["status"], string> = {
  pending: "等待",
  running: "进行中",
  passed: "通过",
  failed: "未过",
  errored: "异常",
}

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  correction_followup: "追问式修正",
  mode_switch_reask: "模式切换重问",
  evidence_gap: "证据缺口",
}

function statusBadge(status: EvalCaseProgress["status"]) {
  if (status === "running") {
    return (
      <Badge variant="outline" className="gap-1">
        <Spinner className="size-3" />
        {STATUS_LABELS[status]}
      </Badge>
    )
  }
  if (status === "passed") return <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400">✓ {STATUS_LABELS[status]}</Badge>
  if (status === "errored") return <Badge variant="destructive">⚠ {STATUS_LABELS[status]}</Badge>
  if (status === "failed") return <Badge variant="destructive">✗ {STATUS_LABELS[status]}</Badge>
  return <Badge variant="secondary">{STATUS_LABELS[status]}</Badge>
}

function formatLatency(ms: unknown) {
  if (typeof ms !== "number" || Number.isNaN(ms)) return "-"
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`
}

function formatPercent(value: unknown) {
  return typeof value === "number" ? `${(value * 100).toFixed(0)}%` : "-"
}

function avgMetric(
  cases: unknown,
  key: string,
  format: (value: unknown) => string,
): string {
  if (!Array.isArray(cases)) return "-"
  const values = cases
    .map((item) => (item as Record<string, unknown>).diagnostics)
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => item[key])
    .filter((value): value is number => typeof value === "number" && !Number.isNaN(value))
  if (!values.length) return "-"
  return format(values.reduce((sum, value) => sum + value, 0) / values.length)
}

function categoryRows(cases: unknown) {
  if (!Array.isArray(cases) || !cases.length) return null
  const groups = new Map<string, { total: number; passed: number }>()
  for (const item of cases) {
    const record = item as Record<string, unknown>
    const category = String(record.category ?? "")
    const group = groups.get(category) ?? { total: 0, passed: 0 }
    group.total += 1
    if (record.completed === true) group.passed += 1
    groups.set(category, group)
  }
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">分类通过情况</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>分类</TableHead>
              <TableHead className="text-right">用例数</TableHead>
              <TableHead>完成比例</TableHead>
              <TableHead>未过用例</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...groups.entries()].map(([category, group]) => {
              const failed = (cases as Array<Record<string, unknown>>)
                .filter((item) => item.category === category && item.completed !== true)
                .map((item) => String(item.case_id))
              return (
                <TableRow key={category}>
                  <TableCell className="font-mono text-xs">{category}</TableCell>
                  <TableCell className="text-right tabular-nums">{group.total}</TableCell>
                  <TableCell>
                    <div className="barcell">
                      <div className="bartrack">
                        <div
                          className="bar"
                          style={{ width: `${(group.passed / group.total) * 100}%` }}
                        />
                      </div>
                      <span className="barlabel">
                        {group.passed}/{group.total}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {failed.join(", ") || "-"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </CardContent>
      <style>{`
        .barcell { display: flex; align-items: center; gap: 8px; min-width: 180px; }
        .bartrack { flex: 1; height: 8px; background: color-mix(in srgb, currentColor 8%, transparent); border-radius: 4px; }
        .bar { height: 8px; border-radius: 0 4px 4px 0; background: var(--color-primary, #2a78d6); }
        .barlabel { font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; color: color-mix(in srgb, currentColor 65%, transparent); }
      `}</style>
    </Card>
  )
}

function FeedbackFindingsSection() {
  const findings = useFeedbackFindings()
  const exportCase = useExportFeedbackCase()
  const [draft, setDraft] = useState<FeedbackCaseDraft | null>(null)

  const handleExport = async (findingId: string) => {
    try {
      setDraft(await exportCase.mutateAsync(findingId))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出评测草稿失败")
    }
  }

  const handleCopy = async () => {
    if (!draft) return
    try {
      await navigator.clipboard.writeText(draft.jsonl_line)
      toast.success("已复制 JSONL 行，请审核后并入 fixture")
    } catch {
      toast.error("复制失败，请手动选择文本复制")
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">反馈发现（人审转评测）</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          研究会话中重复出现的修正信号（确定性规则捕获，仅存摘要与摘要指纹）。
          导出的是评测用例草稿，需操作者审核后手工并入 fixture，不会自动写入。
        </p>
        {findings.data?.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>信号类型</TableHead>
                <TableHead className="text-right">次数</TableHead>
                <TableHead>最近样例</TableHead>
                <TableHead>涉及文档</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {findings.data.map((finding) => (
                <TableRow key={finding.finding_id}>
                  <TableCell className="text-xs">
                    {SIGNAL_TYPE_LABELS[finding.signal_type] ?? finding.signal_type}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{finding.repeat_count}</TableCell>
                  <TableCell className="max-w-72 truncate text-xs text-muted-foreground">
                    {finding.latest_prompt_preview || "-"}
                  </TableCell>
                  <TableCell className="max-w-40 truncate font-mono text-xs text-muted-foreground">
                    {finding.doc_uid || finding.related_doc_uids.join(", ") || "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={exportCase.isPending}
                      onClick={() => void handleExport(finding.finding_id)}
                    >
                      导出用例草稿
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-muted-foreground">
            {findings.isLoading ? "加载中…" : "暂无达到重复阈值的反馈发现。"}
          </p>
        )}
        {draft && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                草稿已生成（建议路径 {draft.suggested_fixture_path}），请人工审核。
              </p>
              <Button size="sm" variant="outline" onClick={() => void handleCopy()}>
                复制 JSONL 行
              </Button>
            </div>
            <pre className="max-h-40 overflow-auto rounded-md bg-muted p-2 text-xs whitespace-pre-wrap break-all">
              {draft.jsonl_line}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function EvalsPage() {
  const [trials, setTrials] = useState("1")
  const [activeUid, setActiveUid] = useState<string | null>(null)
  const runs = useEvalRuns()
  const run = useEvalRun(activeUid)
  const startEval = useStartEvalRun()

  useEffect(() => {
    if (!activeUid && runs.data?.length) {
      const running = runs.data.find((item) => item.status === "running")
      setActiveUid((running ?? runs.data[runs.data.length - 1]!).uid)
    }
  }, [activeUid, runs.data])

  const snapshot = run.data
  const anyRunning = runs.data?.some((item) => item.status === "running") ?? false
  const report = (snapshot?.report ?? null) as Record<string, unknown> | null

  const handleStart = async () => {
    try {
      const created = await startEval.mutateAsync({ trials: Number(trials) })
      setActiveUid(created.uid)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "启动评测失败")
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">任务完成度评测</h1>
          <p className="text-sm text-muted-foreground">
            真实模型全量跑批；过程契约 + LLM 裁判双层判分，支持 pass^k 重复试验。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={trials} onValueChange={setTrials}>
            <SelectTrigger className="w-28" aria-label="每用例试验次数">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 次试验</SelectItem>
              <SelectItem value="3">3 次 (pass^k)</SelectItem>
              <SelectItem value="5">5 次 (pass^k)</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => void handleStart()} disabled={startEval.isPending || anyRunning}>
            {startEval.isPending || anyRunning ? "评测运行中" : "开始评测"}
          </Button>
        </div>
      </div>

      {runs.data && runs.data.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {[...runs.data].reverse().map((item) => (
            <Button
              key={item.uid}
              size="sm"
              variant={item.uid === activeUid ? "default" : "outline"}
              onClick={() => setActiveUid(item.uid)}
            >
              {item.uid.slice(0, 6)} · {item.status === "running" ? "进行中" : item.completed_cases}/{item.total_cases}
            </Button>
          ))}
        </div>
      )}

      {snapshot?.error && (
        <Card className="border-destructive/40">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-destructive">运行失败</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">{snapshot.error}</CardContent>
        </Card>
      )}

      {snapshot && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-sm">
              <span>
                运行 {snapshot.uid.slice(0, 6)}
                {snapshot.trials > 1 && ` · ${snapshot.trials} 次试验/用例`}
              </span>
              <span className="text-muted-foreground">
                {snapshot.completed_cases}/{snapshot.total_cases} 完成 · {snapshot.finished_cases} 已跑
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用例</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">证据</TableHead>
                  <TableHead className="text-right">委派</TableHead>
                  <TableHead className="text-right">时延</TableHead>
                  <TableHead>说明</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshot.cases.map((item) => {
                  const summary = item.summary as Record<string, unknown>
                  const trialInfo = summary.trials as { passed_trials?: number; count?: number } | undefined
                  return (
                    <TableRow key={item.case_id}>
                      <TableCell className="font-mono text-xs">{item.case_id}</TableCell>
                      <TableCell>
                        {statusBadge(item.status)}
                        {item.status === "running" && item.activity ? (
                          <div className="mt-1 text-xs text-muted-foreground tabular-nums">
                            工具调用 {String(item.activity.tool_calls ?? 0)} · 结果{" "}
                            {String(item.activity.tool_results ?? 0)}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {typeof summary.evidence_count === "number" ? `${summary.evidence_count}/${summary.evidence_required ?? 0}` : "-"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {typeof summary.delegation_count === "number" ? `${summary.delegation_count}` : "-"}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{formatLatency(summary.run_latency_ms)}</TableCell>
                      <TableCell className="max-w-64 truncate text-xs text-muted-foreground">
                        {trialInfo && trialInfo.count ? `试验 ${trialInfo.passed_trials}/${trialInfo.count}` : ""}
                        {typeof summary.failure_reason === "string" && summary.failure_reason ? summary.failure_reason : ""}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {report && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            {(
              [
                ["完成率", report.completion_rate],
                ["结果层通过", report.final_success_rate],
                ["过程层通过", report.process_success_rate],
                ["证据覆盖", report.evidence_coverage_rate],
                ["计划完成度", report.average_execution_completion_ratio],
              ] as Array<[string, unknown]>
            ).map(([label, value]) => (
              <Card key={label}>
                <CardContent className="space-y-1">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="text-xl font-semibold tabular-nums">{formatPercent(value)}</div>
                </CardContent>
              </Card>
            ))}
            {[
              ["平均时延", avgMetric(report.cases, "run_latency_ms", (v) => formatLatency(v))],
              [
                "平均工具调用",
                avgMetric(report.cases, "total_tool_calls", (v) =>
                  typeof v === "number" ? v.toFixed(1) : "-",
                ),
              ],
            ].map(([label, value]) => (
              <Card key={label}>
                <CardContent className="space-y-1">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="text-xl font-semibold tabular-nums">{value}</div>
                </CardContent>
              </Card>
            ))}
          </div>
          {categoryRows(report.cases)}
        </div>
      )}

      <FeedbackFindingsSection />
    </div>
  )
}
