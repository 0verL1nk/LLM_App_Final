/**
 * @typedef {{ isPackaged: boolean, getVersion: () => string }} ElectronApp
 * @typedef {{ checkForUpdates: () => Promise<unknown>, downloadUpdate: () => Promise<unknown>, quitAndInstall: (isSilent: boolean, isForceRunAfter: boolean) => void, on: (event: string, listener: (...args: unknown[]) => void) => void, autoDownload: boolean, autoInstallOnAppQuit: boolean, setFeedURL?: (url: string) => void }} ElectronUpdater
 * @typedef {{ status: "downloading" | "progress" | "ready" | "failed", stage?: "check" | "download", version?: string, percent?: number, transferred?: number, total?: number, bytesPerSecond?: number }} UpdateStatus
 */

/**
 * Native package managers own DEB updates. AppImage is the only Linux target
 * that carries its own updater; NSIS and signed macOS builds use GitHub
 * release metadata through electron-updater.
 * @param {{ isPackaged: boolean, platform: NodeJS.Platform, appImage?: string }} runtime
 * @returns {boolean}
 */
function supportsAutomaticUpdates({ isPackaged, platform, appImage }) {
  return isPackaged && (platform === "win32" || platform === "darwin" || (platform === "linux" && Boolean(appImage)))
}

/** @param {{ isPackaged: boolean, platform: NodeJS.Platform, appImage?: string }} runtime */
function unsupportedUpdateReason({ isPackaged, platform, appImage }) {
  if (!isPackaged) return "development"
  if (platform === "linux" && !appImage) return "system-managed"
  return "unavailable"
}

/**
 * @param {{ app: ElectronApp, autoUpdater: ElectronUpdater, logger?: Pick<Console, "error">, notify?: (status: UpdateStatus) => void, notifySystem?: () => void, platform?: NodeJS.Platform, appImage?: string, checkIntervalMs?: number }} dependencies
 * @returns {{ checkForUpdates: () => Promise<{ supported: boolean, status: "unsupported" | "up-to-date" | "available" | "failed", version?: string, reason?: "development" | "system-managed" | "unavailable" }>, installUpdate: () => { supported: boolean, status: "unsupported" | "not-ready" | "installing", reason?: "development" | "system-managed" | "unavailable" }, scheduleCheck: () => void }}
 */
function createUpdateService({ app, autoUpdater, logger = console, notify = () => undefined, notifySystem = () => undefined, platform = process.platform, appImage = process.env.APPIMAGE, checkIntervalMs = 6 * 60 * 60 * 1000, mirrorFeed = "", checkRetryDelayMs = 30_000, schedule = (callback, delay) => setTimeout(callback, delay), interval = (callback, delay) => setInterval(callback, delay) }) {
  const supported = supportsAutomaticUpdates({ isPackaged: app.isPackaged, platform, appImage })
  let checking = false
  let downloading = false
  let readyToInstall = false
  let feedSwitchedToMirror = false
  const reportError = (error) => logger.error("PaperSage update check failed", error)
  const download = async (version) => {
    if (downloading) return
    downloading = true
    readyToInstall = false
    notify({ status: "downloading", version })
    try {
      await autoUpdater.downloadUpdate()
    } catch (error) {
      reportError(error)
      notify({ status: "failed", stage: "download" })
    } finally {
      downloading = false
    }
  }

  const installUpdate = () => {
    if (!supported) return { supported: false, status: "unsupported", reason: unsupportedUpdateReason({ isPackaged: app.isPackaged, platform, appImage }) }
    if (!readyToInstall) return { supported: true, status: "not-ready" }
    // Silent install plus relaunch: the app comes back on the new version,
    // so the user never waits in the dark after quitting. Tell them first —
    // the window closes immediately and the install gap is otherwise silent.
    notifySystem()
    autoUpdater.quitAndInstall(true, true)
    return { supported: true, status: "installing" }
  }

  if (supported) {
    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = true
    autoUpdater.on("error", (error) => {
      reportError(error)
      if (downloading) notify({ status: "failed", stage: "download" })
    })
    autoUpdater.on("update-available", async (info) => { await download(info.version) })
    autoUpdater.on("download-progress", (progress) => notify({
      status: "progress",
      percent: Number(progress.percent || 0),
      transferred: Number(progress.transferred || 0),
      total: Number(progress.total || 0),
      bytesPerSecond: Number(progress.bytesPerSecond || 0),
    }))
    autoUpdater.on("update-downloaded", () => {
      readyToInstall = true
      notify({ status: "ready" })
    })
  }

  const checkWithFeed = async (feed) => {
    if (feed && typeof autoUpdater.setFeedURL === "function") autoUpdater.setFeedURL(feed)
    return autoUpdater.checkForUpdates()
  }

  const checkForUpdates = async () => {
    if (!supported || checking) return {
      supported,
      status: "unsupported",
      reason: unsupportedUpdateReason({ isPackaged: app.isPackaged, platform, appImage }),
    }
    checking = true
    try {
      const result = await checkWithFeed(null)
      const version = String(result?.updateInfo?.version || "")
      return { supported, status: version && version !== app.getVersion() ? "available" : "up-to-date", version: version || undefined }
    } catch (primaryError) {
      // GitHub-hosted feeds are unreachable from some networks; a configured
      // mirror gets one attempt before the check surfaces as failed.
      if (mirrorFeed && !feedSwitchedToMirror) {
        feedSwitchedToMirror = true
        reportError(primaryError)
        try {
          const result = await checkWithFeed(mirrorFeed)
          const version = String(result?.updateInfo?.version || "")
          return { supported, status: version && version !== app.getVersion() ? "available" : "up-to-date", version: version || undefined }
        } catch (mirrorError) {
          reportError(mirrorError)
        }
      } else {
        reportError(primaryError)
      }
      notify({ status: "failed", stage: "check" })
      return { supported, status: "failed" }
    } finally { checking = false }
  }

  return {
    checkForUpdates,
    installUpdate,
    scheduleCheck: () => {
      if (!supported) return
      const runCheck = () => {
        void checkForUpdates().then((result) => {
          // One deferred retry per scheduled cycle: transient DNS/TLS hiccups
          // should not cost a whole six-hour interval.
          if (result.status === "failed") schedule(() => { void checkForUpdates() }, checkRetryDelayMs)
        })
      }
      schedule(runCheck, 12_000)
      // Sessions that stay open for days would otherwise never see a release.
      interval(() => { runCheck() }, checkIntervalMs)
    },
  }
}

module.exports = { createUpdateService, supportsAutomaticUpdates, unsupportedUpdateReason }
