import type { MindmapNode } from "@/lib/a2ui"

// Mirrors the backend fragment caps, but enforces them by truncation instead
// of dropping the whole map: the renderer owns presentation limits.
const MAX_CHILDREN = 12
const MAX_LABEL_LENGTH = 120

export type ResearchMap = {
  title: string
  root: MindmapNode
}

function parseNodeElement(element: Element): MindmapNode | null {
  const label = (element.getAttribute("label") ?? "").trim().slice(0, MAX_LABEL_LENGTH)
  if (!label) return null
  const children: MindmapNode[] = []
  const citations: string[] = []
  for (const child of Array.from(element.children)) {
    if (child.tagName === "node") {
      const parsed = parseNodeElement(child)
      if (parsed) children.push(parsed)
    } else if (child.tagName === "evidence") {
      const reference = (child.getAttribute("ref") ?? "").trim()
      if (reference && !citations.includes(reference)) citations.push(reference)
    }
  }
  return {
    label,
    children: children.slice(0, MAX_CHILDREN),
    citationIds: citations,
  }
}

/**
 * Parse one research-map fragment exactly as the model authored it.
 * Returns null only when the structure is unrecognizable; presentation
 * limits are enforced by truncation so a slightly chatty map still renders.
 */
export function parseResearchMap(xml: string): ResearchMap | null {
  const source = (xml ?? "").trim()
  if (!source) return null
  const document = new DOMParser().parseFromString(source, "text/xml")
  if (document.getElementsByTagName("parsererror").length > 0) return null
  const root = document.documentElement
  if (!root || root.tagName !== "map") return null
  const title = (root.getAttribute("title") ?? "").trim().slice(0, MAX_LABEL_LENGTH)
  const nodeElements = Array.from(root.children).filter((child) => child.tagName === "node")
  if (!title || nodeElements.length < 1) return null
  const rootNode = parseNodeElement(nodeElements[0])
  if (!rootNode) return null
  return { title, root: rootNode }
}
