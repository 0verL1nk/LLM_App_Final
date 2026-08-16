import { applyA2UIEnvelope, applyA2UISurfaceMetadata, type A2UISurface } from "@/lib/a2ui"
import type { AgentEvent } from "@/lib/schemas"
import type { RunItemsResponse } from "@/lib/run-items"

export type RenderedMessagePart =
  | { id: string; type: "markdown"; text: string }
  | { id: string; type: "reasoning"; text: string }
  | { id: string; type: "a2ui"; surfaceId?: string }

export type LiveRunItem = NonNullable<AgentEvent["item"]> & { sequence?: number; order?: number; updatedAt?: string }

export type LiveRun = {
  events: AgentEvent[]
  items: Record<string, LiveRunItem>
  itemOrder: string[]
  parts: RenderedMessagePart[]
  surfaces: Record<string, A2UISurface>
  status: "in_progress" | "completed" | "failed" | "cancelled"
  lastSequence: number
  pendingBySequence: Record<number, AgentEvent>
}

export function createLiveRun(runId?: string): LiveRun {
  void runId
  return { events: [], items: {}, itemOrder: [], parts: [], surfaces: {}, status: "in_progress", lastSequence: 0, pendingBySequence: {} }
}

function applyEvent(run: LiveRun, event: AgentEvent): LiveRun {
  if (event.version === 2 && event.item) {
    return applyItemEvent(run, event)
  }
  if (event.eventType === "message.part.delta") {
    const partId = String(event.payload.partId ?? "text-0")
    const text = String(event.payload.text ?? "")
    const existing = run.parts.find((part) => part.id === partId)
    const parts = existing?.type === "markdown" || existing?.type === "reasoning"
      ? run.parts.map((part) => part.id === partId && (part.type === "markdown" || part.type === "reasoning") ? { ...part, text: part.text + text } : part)
      : [...run.parts, { id: partId, type: "markdown" as const, text }]
    // Keep one arrival marker per part so run.events preserves the chronology
    // between streamed text and tool/item activity.
    return { ...run, parts, events: existing ? run.events : [...run.events, event] }
  }
  if (event.eventType === "message.part.insert") {
    const partId = String(event.payload.partId ?? "")
    const partType = event.payload.type === "reasoning" ? "reasoning" : "a2ui"
    const known = !partId || run.parts.some((part) => part.id === partId)
    const parts = known
      ? run.parts
      : partType === "reasoning"
        ? [...run.parts, { id: partId, type: "reasoning" as const, text: "" }]
        : [...run.parts, { id: partId, type: "a2ui" as const }]
    return { ...run, parts, events: known ? run.events : [...run.events, event] }
  }
  if (event.eventType === "presentation.failed") {
    const partId = String(event.payload.partId ?? "")
    return {
      ...run,
      parts: run.parts.filter((part) => part.id !== partId),
      events: [...run.events, event],
    }
  }
  if (event.eventType === "ui.a2ui") {
    const metadata = event.payload.surface && typeof event.payload.surface === "object"
      ? event.payload.surface as Record<string, unknown>
      : null
    const previousSurfaceId = typeof metadata?.surfaceId === "string" ? metadata.surfaceId : ""
    const nextSurface = applyA2UISurfaceMetadata(
      applyA2UIEnvelope(run.surfaces[previousSurfaceId] ?? null, event.payload.envelope),
      metadata,
    )
    const surfaces = { ...run.surfaces }
    if (nextSurface) surfaces[nextSurface.surfaceId] = nextSurface
    else if (previousSurfaceId) delete surfaces[previousSurfaceId]
    const partId = typeof metadata?.partId === "string" ? metadata.partId : ""
    const parts = partId && nextSurface
      ? run.parts.map((part) => part.id === partId && part.type === "a2ui" ? { ...part, surfaceId: nextSurface.surfaceId } : part)
      : run.parts
    return { ...run, surfaces, parts }
  }
  const runStatus = _runStatusFrom(event.eventType)
  return runStatus ? { ...run, status: runStatus, events: [...run.events, event] } : { ...run, events: [...run.events, event] }
}

function applyItemEvent(run: LiveRun, event: AgentEvent): LiveRun {
  const item = event.item
  if (!item) return run
  const payload = item.payload
  if (item.type === "assistant_message" || item.type === "reasoning_summary") {
    const partId = String(payload.partId ?? item.id)
    const type = item.type === "reasoning_summary" ? "reasoning" as const : "markdown" as const
    const delta = String(payload.delta ?? "")
    const previous = run.items[item.id]
    const accumulated = delta
      ? String(previous?.payload?.text ?? "") + delta
      : String(payload.text ?? previous?.payload?.text ?? "")
    const projected: LiveRunItem = { ...item, payload: { ...payload, text: accumulated } }
    const items = { ...run.items, [item.id]: projected }
    const itemOrder = run.itemOrder.includes(item.id) ? run.itemOrder : [...run.itemOrder, item.id]
    const existing = run.parts.find((part) => part.id === partId)
    const parts = existing?.type === type
      ? run.parts.map((part) => part.id === partId && part.type === type ? { ...part, text: accumulated } : part)
      : [...run.parts, { id: partId, type, text: accumulated }]
    // One arrival marker per part keeps run.events a usable chronology log.
    return { ...run, items, itemOrder, parts, events: existing ? run.events : [...run.events, event] }
  }
  const items = { ...run.items, [item.id]: item }
  const itemOrder = run.itemOrder.includes(item.id) ? run.itemOrder : [...run.itemOrder, item.id]
  if (item.type === "presentation") {
    const partId = String(payload.partId ?? item.id)
    const metadata = payload.surface && typeof payload.surface === "object"
      ? payload.surface as Record<string, unknown>
      : null
    const surfaceId = typeof metadata?.surfaceId === "string" ? metadata.surfaceId : ""
    const nextSurface = payload.envelope && typeof payload.envelope === "object"
      ? applyA2UISurfaceMetadata(
        applyA2UIEnvelope(run.surfaces[surfaceId] ?? null, payload.envelope),
        metadata,
      )
      : null
    const surfaces = { ...run.surfaces }
    if (nextSurface) surfaces[nextSurface.surfaceId] = nextSurface
    const parts = run.parts.some((part) => part.id === partId)
      ? run.parts.map((part) => part.id === partId && part.type === "a2ui" && nextSurface ? { ...part, surfaceId: nextSurface.surfaceId } : part)
      : item.status === "failed"
        ? run.parts
        : [...run.parts, { id: partId, type: "a2ui" as const, surfaceId: nextSurface?.surfaceId }]
    return { ...run, items, itemOrder, surfaces, parts }
  }
  const status = _runStatusFrom(event.eventType)
  return status ? { ...run, status, items, itemOrder, events: [...run.events, event] } : { ...run, items, itemOrder, events: [...run.events, event] }
}

function _runStatusFrom(eventType: string): LiveRun["status"] | null {
  if (eventType === "run.completed") return "completed"
  if (eventType === "run.failed") return "failed"
  if (eventType === "run.cancelled") return "cancelled"
  return null
}

/**
 * Applies durable Run events in sequence order.  A reconnect may replay
 * events, and concurrent stream readers may briefly arrive out of order.
 */
export function reduceLiveRun(run: LiveRun, event: AgentEvent): LiveRun {
  if (event.sequence <= run.lastSequence || run.pendingBySequence[event.sequence]) return run
  const pendingBySequence = { ...run.pendingBySequence, [event.sequence]: event }
  let next = { ...run, pendingBySequence }
  while (next.pendingBySequence[next.lastSequence + 1]) {
    const sequence = next.lastSequence + 1
    const nextEvent = next.pendingBySequence[sequence]
    const remaining = { ...next.pendingBySequence }
    delete remaining[sequence]
    next = { ...applyEvent(next, nextEvent), lastSequence: sequence, pendingBySequence: remaining }
  }
  return next
}

export function liveAnswer(parts: RenderedMessagePart[]): string {
  return parts.reduce((answer, part) => part.type === "markdown" ? answer + part.text : answer, "")
}
export function liveRunItems(run: LiveRun): LiveRunItem[] {
  return run.itemOrder.map((id) => run.items[id]).filter((item): item is LiveRunItem => Boolean(item))
}

export function liveMessageParts(items: LiveRunItem[]): RenderedMessagePart[] {
  const parts: RenderedMessagePart[] = []
  for (const item of items) {
    if (item.type !== "assistant_message" && item.type !== "reasoning_summary") continue
    const partId = String(item.payload?.partId ?? item.id)
    const type = item.type === "reasoning_summary" ? "reasoning" : "markdown"
    const text = String(item.payload?.text ?? "")
    const existing = parts.find((part) => part.id === partId)
    if (existing && (existing.type === "markdown" || existing.type === "reasoning") && existing.type === type) {
      existing.text = text || existing.text
    } else {
      parts.push({ id: partId, type, text })
    }
  }
  return parts
}

export function hydrateLiveRun(run: LiveRun, snapshot: RunItemsResponse): LiveRun {
  const items: Record<string, LiveRunItem> = { ...run.items }
  const itemOrder = [...run.itemOrder]
  for (const item of snapshot.items) {
    items[item.id] = { id: item.id, type: item.type, status: item.status, taskId: item.taskId, payload: item.payload }
    if (!itemOrder.includes(item.id)) itemOrder.push(item.id)
  }
  const parts = liveMessageParts(itemOrder.map((id) => items[id]).filter(Boolean))
  return {
    ...run,
    items,
    itemOrder,
    parts: run.parts.length ? run.parts : parts,
    lastSequence: Math.max(run.lastSequence, snapshot.lastSequence ?? 0),
    // The snapshot is authoritative: any events stalled on a sequence gap are
    // superseded (their items are already reflected) and must not re-apply.
    pendingBySequence: {},
  }
}
