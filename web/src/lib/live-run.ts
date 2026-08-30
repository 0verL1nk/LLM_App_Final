import { applyA2UIEnvelope, applyA2UISurfaceMetadata, type A2UISurface } from "@/lib/a2ui"
import type { AgentEvent, Message } from "@/lib/schemas"

export type RenderedMessagePart =
  | { id: string; type: "markdown"; text: string }
  | { id: string; type: "reasoning"; text: string }
  | { id: string; type: "a2ui"; surfaceId?: string }
  | { id: string; type: "component"; component: string; state: string; xml?: string; error?: string }

export type LiveRunItem = NonNullable<AgentEvent["item"]>

export type LiveRun = {
  events: AgentEvent[]
  items: Record<string, LiveRunItem>
  parts: RenderedMessagePart[]
  surfaces: Record<string, A2UISurface>
  lastSequence: number
  pendingBySequence: Record<number, AgentEvent>
}

export function createLiveRun(): LiveRun {
  return { events: [], items: {}, parts: [], surfaces: {}, lastSequence: 0, pendingBySequence: {} }
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
  return { ...run, events: [...run.events, event] }
}

function applyItemEvent(run: LiveRun, event: AgentEvent): LiveRun {
  const item = event.item
  if (!item) return run
  const items = { ...run.items, [item.id]: item }
  const payload = item.payload
  if (item.type === "component") {
    const partId = String(payload.partId ?? item.id)
    const component = String(payload.component ?? "research-map")
    const incomingState = String(payload.state ?? "streaming")
    const delta = typeof payload.delta === "string" ? payload.delta : ""
    const fullXml = typeof payload.xml === "string" ? payload.xml : undefined
    const error = typeof payload.error === "string" ? payload.error : undefined
    const existing = run.parts.find((part) => part.id === partId)
    // Content-only contract: the part keeps the fragment exactly as authored;
    // "streaming" never overwrites a terminal state on replay.
    const parts = existing?.type === "component"
      ? run.parts.map((part) => part.id === partId && part.type === "component"
        ? {
            ...part,
            state: incomingState === "streaming" ? part.state : incomingState,
            xml: fullXml ?? (part.xml ?? "") + delta,
            error: error ?? part.error,
          }
        : part)
      : [...run.parts, {
          id: partId,
          type: "component" as const,
          component,
          state: incomingState,
          xml: fullXml ?? delta,
          ...(error ? { error } : {}),
        }]
    return { ...run, items, parts, events: existing ? run.events : [...run.events, event] }
  }
  if (item.type === "assistant_message" || item.type === "reasoning_summary") {
    const partId = String(payload.partId ?? item.id)
    const type = item.type === "reasoning_summary" ? "reasoning" as const : "markdown" as const
    const delta = String(payload.delta ?? "")
    const existing = run.parts.find((part) => part.id === partId)
    const parts = existing?.type === type
      ? run.parts.map((part) => part.id === partId && part.type === type ? { ...part, text: delta ? part.text + delta : String(payload.text ?? part.text) } : part)
      : [...run.parts, { id: partId, type, text: delta || String(payload.text ?? "") }]
    // One arrival marker per part keeps run.events a usable chronology log.
    return { ...run, items, parts, events: existing ? run.events : [...run.events, event] }
  }
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
    // A failed presentation never receives envelopes; dropping its placeholder
    // part keeps a skeleton from pulsing until the run refetches.
    const parts = item.status === "failed"
      ? run.parts.filter((part) => part.id !== partId)
      : run.parts.some((part) => part.id === partId)
        ? run.parts.map((part) => part.id === partId && part.type === "a2ui" && nextSurface ? { ...part, surfaceId: nextSurface.surfaceId } : part)
        : [...run.parts, { id: partId, type: "a2ui" as const, surfaceId: nextSurface?.surfaceId }]
    return { ...run, items, surfaces, parts }
  }
  return { ...run, items, events: [...run.events, event] }
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

export function assistantParts(message: Message): RenderedMessagePart[] {
  const stored: RenderedMessagePart[] = []
  message.parts?.forEach((part, index) => {
    const type = part.type
    if (type === "markdown" && typeof part.text === "string") {
      stored.push({ id: typeof part.id === "string" ? part.id : `text-${index}`, type, text: part.text })
      return
    }
    if (type === "reasoning" && typeof part.text === "string") {
      stored.push({ id: typeof part.id === "string" ? part.id : `reasoning-${index}`, type, text: part.text })
      return
    }
    if (type === "a2ui") {
      stored.push({ id: typeof part.id === "string" ? part.id : `surface-${index}`, type, surfaceId: typeof part.surfaceId === "string" ? part.surfaceId : undefined })
      return
    }
    if (type === "component") {
      stored.push({
        id: typeof part.id === "string" ? part.id : `component-${index}`,
        type,
        component: typeof part.component === "string" ? part.component : "research-map",
        state: typeof part.state === "string" ? part.state : "ready",
        xml: typeof part.xml === "string" ? part.xml : undefined,
        error: typeof part.error === "string" ? part.error : undefined,
      })
    }
  })
  if (stored.length) return stored
  const legacySurfaces = Array.isArray(message.a2ui) ? message.a2ui : [message.a2ui]
  return [
    ...(message.content ? [{ id: "text-0", type: "markdown" as const, text: message.content }] : []),
    ...legacySurfaces.flatMap((surface, index) => typeof surface?.surfaceId === "string"
      ? [{ id: `surface-${index}`, type: "a2ui" as const, surfaceId: surface.surfaceId }]
      : []),
  ]
}
