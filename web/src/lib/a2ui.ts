export const MINDMAP_CATALOG_ID = "https://papersage.local/a2ui/catalogs/mindmap-v1.json"

export type MindmapNode = { label: string; children: MindmapNode[] }

export type A2UISurface = {
  surfaceId: string
  catalogId: typeof MINDMAP_CATALOG_ID
  hasMindmapComponent: boolean
  mindmap: MindmapNode | null
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function parseNode(value: unknown, depth = 0): MindmapNode | null {
  const node = record(value)
  const label = typeof node?.label === "string" ? node.label.trim() : ""
  const rawChildren = Array.isArray(node?.children) ? node.children : null
  if (!label || label.length > 120 || !rawChildren || rawChildren.length > 12 || depth > 5) return null
  const children = rawChildren.map((child) => parseNode(child, depth + 1))
  return children.some((child) => child === null) ? null : { label, children: children as MindmapNode[] }
}

export function applyA2UIEnvelope(surface: A2UISurface | null, value: unknown): A2UISurface | null {
  const envelope = record(value)
  if (envelope?.version !== "v0.9") return surface

  const create = record(envelope.createSurface)
  if (create) {
    const surfaceId = typeof create.surfaceId === "string" ? create.surfaceId.trim() : ""
    if (!surfaceId || create.catalogId !== MINDMAP_CATALOG_ID) return surface
    return { surfaceId, catalogId: MINDMAP_CATALOG_ID, hasMindmapComponent: false, mindmap: null }
  }

  if (!surface) return surface
  const updateComponents = record(envelope.updateComponents)
  if (updateComponents) {
    const components = updateComponents.components
    if (updateComponents.surfaceId !== surface.surfaceId || !Array.isArray(components) || components.length !== 1) return surface
    const root = record(components[0])
    const data = record(root?.data)
    if (root?.id !== "root" || root.component !== "Mindmap" || data?.path !== "/mindmap") return surface
    return { ...surface, hasMindmapComponent: true }
  }

  const updateData = record(envelope.updateDataModel)
  if (updateData) {
    if (!surface.hasMindmapComponent || updateData.surfaceId !== surface.surfaceId || updateData.path !== "/mindmap") return surface
    const mindmap = parseNode(updateData.value)
    return mindmap ? { ...surface, mindmap } : surface
  }

  const remove = record(envelope.deleteSurface)
  return remove?.surfaceId === surface.surfaceId ? null : surface
}

export function surfaceFromPersisted(value: Record<string, unknown> | null | undefined): A2UISurface | null {
  if (!value) return null
  const messages = Array.isArray(value.messages) ? value.messages : []
  const replayed = messages.reduce<A2UISurface | null>((surface, envelope) => applyA2UIEnvelope(surface, envelope), null)
  if (replayed?.mindmap) return replayed
  const surfaceId = typeof value.surfaceId === "string" ? value.surfaceId : ""
  const mindmap = parseNode(value.mindmap)
  return surfaceId && value.catalogId === MINDMAP_CATALOG_ID && mindmap
    ? { surfaceId, catalogId: MINDMAP_CATALOG_ID, hasMindmapComponent: true, mindmap }
    : null
}
