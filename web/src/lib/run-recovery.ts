import { api } from "@/lib/api";
import { z } from "zod";

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
