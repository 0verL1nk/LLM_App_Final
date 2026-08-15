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

test("installUpdate restarts into a downloaded update and refuses anything else", async () => {
  const listeners = {}
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => ({ updateInfo: { version: "1.2.0" } }),
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: (event, listener) => { listeners[event] = listener },
  }
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    platform: "win32",
  })

  assert.deepEqual(service.installUpdate(), { supported: true, status: "not-ready" })

  await listeners["update-available"]({ version: "1.2.0" })
  await listeners["update-downloaded"]()

  let installed = null
  updater.quitAndInstall = (isSilent, isForceRunAfter) => { installed = { isSilent, isForceRunAfter } }
  assert.deepEqual(service.installUpdate(), { supported: true, status: "installing" })
  assert.deepEqual(installed, { isSilent: true, isForceRunAfter: true })
})

test("installUpdate is unsupported where automatic updates are unavailable", async () => {
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => ({ updateInfo: {} }),
    downloadUpdate: async () => undefined,
    quitAndInstall: () => { throw new Error("must not install") },
    on: () => undefined,
  }
  const service = createUpdateService({
    app: { isPackaged: false, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    platform: "win32",
  })

  assert.deepEqual(service.installUpdate(), { supported: false, status: "unsupported", reason: "development" })
})

test("scheduleCheck rechecks periodically so long-running sessions still see releases", async (t) => {
  const calls = []
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => { calls.push(calls.length); return { updateInfo: { version: "1.1.8" } } },
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

  t.mock.timers.enable({ apis: ["setTimeout", "setInterval"] })
  service.scheduleCheck()
  await t.mock.timers.tick(12_000)
  assert.equal(calls.length, 1)
  await t.mock.timers.tick(6 * 60 * 60 * 1000)
  assert.equal(calls.length, 2)
  await t.mock.timers.tick(6 * 60 * 60 * 1000)
  assert.equal(calls.length, 3)
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

test("installUpdate announces the restart before the window disappears", async () => {
  const listeners = {}
  const events = []
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => ({ updateInfo: { version: "1.2.0" } }),
    downloadUpdate: async () => undefined,
    quitAndInstall: () => { events.push("install") },
    on: (event, listener) => { listeners[event] = listener },
  }
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    notifySystem: () => { events.push("notify") },
    platform: "win32",
  })

  await listeners["update-available"]({ version: "1.2.0" })
  await listeners["update-downloaded"]()

  assert.deepEqual(service.installUpdate(), { supported: true, status: "installing" })
  assert.deepEqual(events, ["notify", "install"])
})
