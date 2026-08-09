import { applyA2UIEnvelope, applyA2UISurfaceMetadata, type A2UISurface } from "@/lib/a2ui"
import type { AgentEvent } from "@/lib/schemas"

export type RenderedMessagePart =
  | { id: string; type: "markdown"; text: string }
  | { id: string; type: "a2ui"; surfaceId?: string }

export type LiveRun = {
  events: AgentEvent[]
  parts: RenderedMessagePart[]
  surfaces: Record<string, A2UISurface>
  lastSequence: number
  pendingBySequence: Record<number, AgentEvent>
}

export function createLiveRun(): LiveRun {
  return { events: [], parts: [], surfaces: {}, lastSequence: 0, pendingBySequence: {} }
}

function applyEvent(run: LiveRun, event: AgentEvent): LiveRun {
  if (event.eventType === "message.part.delta") {
    const partId = String(event.payload.partId ?? "text-0")
    const text = String(event.payload.text ?? "")
    const existing = run.parts.find((part) => part.id === partId)
    const parts = existing?.type === "markdown"
      ? run.parts.map((part) => part.id === partId && part.type === "markdown" ? { ...part, text: part.text + text } : part)
      : [...run.parts, { id: partId, type: "markdown" as const, text }]
    return { ...run, parts }
  }
  if (event.eventType === "message.part.insert") {
    const partId = String(event.payload.partId ?? "")
    const parts = !partId || run.parts.some((part) => part.id === partId)
      ? run.parts
      : [...run.parts, { id: partId, type: "a2ui" as const }]
    return { ...run, parts }
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
  return { ...run, events: [...run.events, event] }
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
