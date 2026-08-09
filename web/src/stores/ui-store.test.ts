import { afterEach, describe, expect, it } from "vitest"

import { useUiStore } from "@/stores/ui-store"

describe("ui store", () => {
  afterEach(() => useUiStore.setState({ currentProjectId: "", desktopUpdate: { phase: "idle" } }))

  it("keeps the active project available while visiting a global page", () => {
    useUiStore.getState().setCurrentProjectId("project-123")

    expect(useUiStore.getState().currentProjectId).toBe("project-123")
  })

  it("retains a desktop download progress update while the active project changes", () => {
    useUiStore.getState().setDesktopUpdate({ phase: "downloading", percent: 58, transferred: 58, total: 100 })
    useUiStore.getState().setCurrentProjectId("project-456")

    expect(useUiStore.getState().desktopUpdate).toMatchObject({ phase: "downloading", percent: 58 })
  })
})
