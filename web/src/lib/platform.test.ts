import { afterEach, describe, expect, it, vi } from "vitest"

import { desktopWindowControls } from "@/lib/platform"

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("desktopWindowControls", () => {
  it("keeps the browser build free of desktop-only capabilities", () => {
    expect(desktopWindowControls()).toBeUndefined()
  })

  it("returns only the explicitly preloaded desktop controls", () => {
    const controls = { minimize: async () => undefined, toggleMaximize: async () => false, close: async () => undefined, checkForUpdates: async () => ({ supported: true, status: "up-to-date" as const }), openLogs: async () => "", onUpdateStatus: () => () => undefined }
    vi.stubGlobal("window", { papersageDesktop: controls })
    expect(desktopWindowControls()).toBe(controls)
  })
})
