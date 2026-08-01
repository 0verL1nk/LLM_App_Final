const test = require("node:test")
const assert = require("node:assert/strict")
const { createUpdateService, supportsAutomaticUpdates } = require("./updater.cjs")

test("automatic updates require a packaged supported target", () => {
  assert.equal(supportsAutomaticUpdates({ isPackaged: false, platform: "win32" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "win32" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "darwin" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux", appImage: "/tmp/PaperSage.AppImage" }), true)
})

test("manual checks return an explicit current or available version result", async () => {
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => ({ updateInfo: { version: "1.2.0" } }),
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: () => undefined,
  }
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    dialog: { showMessageBox: async () => ({ response: 1 }) },
    logger: { error: () => undefined },
    platform: "win32",
  })

  assert.deepEqual(await service.checkForUpdates(), { supported: true, status: "available", version: "1.2.0" })
  updater.checkForUpdates = async () => ({ updateInfo: { version: "1.1.8" } })
  assert.deepEqual(await service.checkForUpdates(), { supported: true, status: "up-to-date", version: "1.1.8" })
})
