import { useEffect, useRef } from "react"

import { api, consumeEventStream } from "@/lib/api"
import { agentEventSchema, turnResultSchema } from "@/lib/schemas"
import type { AgentEvent, TurnResult } from "@/lib/schemas"
import { z } from "zod"

export type RunTaskAction = "cancel" | "retry";

/** Persisted V2 item snapshot plus its event-sequence replay cursor. */
export type RunSnapshot = { items: unknown[]; lastSequence: number };

/**
 * Fetch the durable item snapshot for one run. Returns null when the run has
 * no snapshot yet or the request fails — snapshot hydration is best-effort and
 * a full afterSeq=0 replay still recovers the view.
 */
export async function fetchRunSnapshot(runUid: string, signal: AbortSignal): Promise<RunSnapshot | null> {
  try {
    const response = await fetch(`/api/v1/runs/${runUid}/items`, {
      headers: { "X-User-Id": "local-user" },
      signal,
    });
    if (!response.ok) return null;
    const envelope = (await response.json()) as { data?: unknown; lastSequence?: number };
    return {
      items: Array.isArray(envelope.data) ? envelope.data : [],
      lastSequence: Number(envelope.lastSequence ?? 0),
    };
  } catch {
    return null;
  }
}

/** Request a durable task cancellation or requeue; throws with a server message. */
export async function postTaskAction(taskUid: string, action: RunTaskAction): Promise<void> {
  await api(`/tasks/${taskUid}/${action === "cancel" ? "cancel" : "retry"}`, z.unknown(), { method: "POST" });
}


// How often the watchdog checks for streams stalled on a sequence gap before
// re-syncing from the authoritative server snapshot.
const GAP_RESYNC_INTERVAL_MS = 10_000

export type RunRecoveryOptions = {
  runs: { run_uid: string }[] | undefined
  ensureRun: (runId: string) => void
  applyEvent: (event: AgentEvent) => void
  hydrateSnapshot: (runId: string, snapshot: RunSnapshot) => void
  stalledRunIds: () => string[]
  onCompleted: (result: TurnResult) => void
  onTerminalCleanup: (runId: string) => void
  onRecoveryError: (error: unknown) => void
}

/**
 * Reconnect flow for in-flight runs: hydrate the persisted item snapshot,
 * subscribe strictly after its cursor, and resync from the snapshot when a
 * stream stalls on a sequence gap (mixed V1/V2 history) instead of freezing.
 */
export function useRunRecovery(options: RunRecoveryOptions): void {
  const resumed = useRef(new Set<string>())
  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  })
  useEffect(() => {
    const controller = new AbortController()
    const current = optionsRef.current
    for (const run of options.runs ?? []) {
      if (resumed.current.has(run.run_uid)) continue
      resumed.current.add(run.run_uid)
      current.ensureRun(run.run_uid)
      void (async () => {
        const snapshot = await fetchRunSnapshot(run.run_uid, controller.signal)
        if (snapshot) current.hydrateSnapshot(run.run_uid, snapshot)
        await consumeEventStream(
          `/runs/${run.run_uid}/events?afterSeq=${snapshot?.lastSequence ?? 0}`,
          (rawEvent) => {
            const event = agentEventSchema.parse(rawEvent)
            current.applyEvent(event)
            if (event.eventType === "run.completed") {
              current.onCompleted(turnResultSchema.parse(event.payload.result))
              current.onTerminalCleanup(event.runId)
            }
            if (event.eventType === "run.failed") current.onTerminalCleanup(event.runId)
          },
          controller.signal,
        )
      })().catch((error: unknown) => {
        if (controller.signal.aborted) return
        current.onRecoveryError(error)
      })
    }
    return () => controller.abort()
  }, [options.runs])
  useEffect(() => {
    const timer = window.setInterval(() => {
      for (const runId of optionsRef.current.stalledRunIds()) {
        void fetchRunSnapshot(runId, new AbortController().signal).then((snapshot) => {
          if (snapshot) optionsRef.current.hydrateSnapshot(runId, snapshot)
        })
      }
    }, GAP_RESYNC_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [])
}