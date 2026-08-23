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

  const flush = () => new Promise((resolve) => setImmediate(resolve))
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval"] })
  service.scheduleCheck()
  await t.mock.timers.tick(12_000)
  await flush()
  assert.equal(calls.length, 1)
  await t.mock.timers.tick(6 * 60 * 60 * 1000)
  await flush()
  assert.equal(calls.length, 2)
  await t.mock.timers.tick(6 * 60 * 60 * 1000)
  await flush()
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

test("a failing primary feed falls back to a configured mirror once", async () => {
  const calls = []
  const feeds = []
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => {
      calls.push(feeds[feeds.length - 1] ?? "default")
      if (calls.length === 1) throw new Error("network unreachable")
      return { updateInfo: { version: "1.2.0" } }
    },
    setFeedURL: (url) => { feeds.push(url) },
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: () => undefined,
  }
  const statuses = []
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    notify: (status) => statuses.push(status),
    platform: "win32",
    mirrorFeed: "https://mirror.example/papersage",
  })

  const result = await service.checkForUpdates()

  assert.deepEqual(result, { supported: true, status: "available", version: "1.2.0" })
  assert.deepEqual(feeds, ["https://mirror.example/papersage"])
  assert.deepEqual(calls, ["default", "https://mirror.example/papersage"])
  assert.deepEqual(statuses, [])
})

test("a failed check notifies with the check stage", async () => {
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => { throw new Error("network unreachable") },
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: () => undefined,
  }
  const statuses = []
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    notify: (status) => statuses.push(status),
    platform: "win32",
  })

  const result = await service.checkForUpdates()

  assert.deepEqual(result, { supported: true, status: "failed" })
  assert.deepEqual(statuses, [{ status: "failed", stage: "check" }])
})

test("scheduled checks retry once after a failure", async () => {
  const timers = []
  const attempts = []
  const updater = {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    checkForUpdates: async () => {
      attempts.push(1)
      if (attempts.length < 3) throw new Error("network unreachable")
      return { updateInfo: { version: "1.1.8" } }
    },
    downloadUpdate: async () => undefined,
    quitAndInstall: () => undefined,
    on: () => undefined,
  }
  const service = createUpdateService({
    app: { isPackaged: true, getVersion: () => "1.1.8" },
    autoUpdater: updater,
    logger: { error: () => undefined },
    platform: "win32",
    checkRetryDelayMs: 500,
    schedule: (callback) => { timers.push(callback) },
    interval: () => 0,
  })

  service.scheduleCheck()
  assert.equal(timers.length, 1, "the startup check is deferred")
  await timers.shift()()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(timers.length, 1, "a failed check schedules exactly one retry")
  await timers.shift()()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(timers.length, 0, "a successful retry schedules nothing further")
  assert.equal(attempts.length, 2)
})
