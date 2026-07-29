import { describe, expect, it } from "vitest"

import { applyA2UIEnvelope, MINDMAP_CATALOG_ID, surfaceFromPersisted } from "@/lib/a2ui"

const create = { version: "v0.9", createSurface: { surfaceId: "map-1", catalogId: MINDMAP_CATALOG_ID } }
const components = { version: "v0.9", updateComponents: { surfaceId: "map-1", components: [{ id: "root", component: "Mindmap", data: { path: "/mindmap" } }] } }
const data = { version: "v0.9", updateDataModel: { surfaceId: "map-1", path: "/mindmap", value: { label: "论文", children: [{ label: "方法", children: [] }] } } }

describe("A2UI mindmap surface", () => {
  it("replays the ordered v0.9 envelopes into a safe surface", () => {
    const surface = [create, components, data].reduce(applyA2UIEnvelope, null)
    expect(surface?.mindmap).toEqual({ label: "论文", children: [{ label: "方法", children: [] }] })
  })

  it("does not accept a foreign catalog or a data update before the component", () => {
    expect(applyA2UIEnvelope(null, { ...create, createSurface: { ...create.createSurface, catalogId: "https://example.com/catalog" } })).toBeNull()
    const surface = applyA2UIEnvelope(null, create)
    expect(applyA2UIEnvelope(surface, data)?.mindmap).toBeNull()
  })

  it("reconstructs persisted event envelopes and ignores arbitrary fields", () => {
    const surface = surfaceFromPersisted({ messages: [create, components, data], script: "alert(1)" })
    expect(surface?.surfaceId).toBe("map-1")
    expect(surface?.mindmap?.label).toBe("论文")
  })
})
