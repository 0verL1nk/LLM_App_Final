import { afterEach, describe, expect, it } from "vitest"

import { useUiStore } from "@/stores/ui-store"

describe("ui store", () => {
  afterEach(() => useUiStore.setState({ currentProjectId: "" }))

  it("keeps the active project available while visiting a global page", () => {
    useUiStore.getState().setCurrentProjectId("project-123")

    expect(useUiStore.getState().currentProjectId).toBe("project-123")
  })
})
