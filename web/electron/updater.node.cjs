const test = require("node:test")
const assert = require("node:assert/strict")
const { createUpdateService, supportsAutomaticUpdates, unsupportedUpdateReason } = require("./updater.cjs")

test("automatic updates require a packaged supported target", () => {
  assert.equal(supportsAutomaticUpdates({ isPackaged: false, platform: "win32" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "win32" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "darwin" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux", appImage: "/tmp/PaperSage.AppImage" }), true)
  assert.equal(unsupportedUpdateReason({ isPackaged: false, platform: "win32" }), "development")
  assert.equal(unsupportedUpdateReason({ isPackaged: true, platform: "linux" }), "system-managed")
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
    logger: { error: () => undefined },
    platform: "win32",
  })

  assert.deepEqual(await service.checkForUpdates(), { supported: true, status: "available", version: "1.2.0" })
  updater.checkForUpdates = async () => ({ updateInfo: { version: "1.1.8" } })
  assert.deepEqual(await service.checkForUpdates(), { supported: true, status: "up-to-date", version: "1.1.8" })
})

test("downloads silently and schedules installation for the next app exit", async () => {
  const listeners = {}
  const statuses = []
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => ({ updateInfo: { version: "1.2.0" } }),
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: (event, listener) => { listeners[event] = listener },
  }
  createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    notify: (status) => statuses.push(status),
    platform: "win32",
  })

  assert.equal(updater.autoInstallOnAppQuit, true)

  await listeners["update-available"]({ version: "1.2.0" })
  listeners["download-progress"]({ percent: 42.4, transferred: 424, total: 1000, bytesPerSecond: 80 })
  await listeners["update-downloaded"]()

  assert.deepEqual(statuses, [
    { status: "downloading", version: "1.2.0" },
    { status: "progress", percent: 42.4, transferred: 424, total: 1000, bytesPerSecond: 80 },
    { status: "ready" },
  ])
})
