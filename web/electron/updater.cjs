/**
 * @typedef {{ isPackaged: boolean, getVersion: () => string }} ElectronApp
 * @typedef {{ showMessageBox: (options: object) => Promise<{ response: number }> }} ElectronDialog
 * @typedef {{ checkForUpdates: () => Promise<unknown>, downloadUpdate: () => Promise<unknown>, quitAndInstall: () => void, on: (event: string, listener: (...args: unknown[]) => void) => void, autoDownload: boolean, autoInstallOnAppQuit: boolean }} ElectronUpdater
 * @typedef {{ status: "downloading" | "progress" | "ready" | "failed", version?: string, percent?: number, transferred?: number, total?: number, bytesPerSecond?: number }} UpdateStatus
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
 * @param {{ app: ElectronApp, autoUpdater: ElectronUpdater, dialog: ElectronDialog, logger?: Pick<Console, "error">, notify?: (status: UpdateStatus) => void, platform?: NodeJS.Platform, appImage?: string }} dependencies
 * @returns {{ checkForUpdates: () => Promise<{ supported: boolean, status: "unsupported" | "up-to-date" | "available" | "failed", version?: string, reason?: "development" | "system-managed" | "unavailable" }>, scheduleCheck: () => void }}
 */
function createUpdateService({ app, autoUpdater, dialog, logger = console, notify = () => undefined, platform = process.platform, appImage = process.env.APPIMAGE }) {
  const supported = supportsAutomaticUpdates({ isPackaged: app.isPackaged, platform, appImage })
  let checking = false
  let downloading = false
  const reportError = (error) => logger.error("PaperSage update check failed", error)
  const download = async (version) => {
    if (downloading) return
    downloading = true
    notify({ status: "downloading", version })
    try {
      await autoUpdater.downloadUpdate()
    } catch (error) {
      reportError(error)
      notify({ status: "failed" })
    } finally {
      downloading = false
    }
  }

  if (supported) {
    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = true
    autoUpdater.on("error", (error) => {
      reportError(error)
      if (downloading) notify({ status: "failed" })
    })
    autoUpdater.on("update-available", async (info) => {
      const result = await dialog.showMessageBox({ type: "info", title: "发现新版本", message: `PaperSage ${info.version} 已准备好下载。`, detail: "下载期间可以继续使用 PaperSage；完成后会提醒你重启安装。", buttons: ["开始下载", "暂不更新"], defaultId: 0, cancelId: 1 })
      if (result.response === 0) await download(info.version)
    })
    autoUpdater.on("download-progress", (progress) => notify({
      status: "progress",
      percent: Number(progress.percent || 0),
      transferred: Number(progress.transferred || 0),
      total: Number(progress.total || 0),
      bytesPerSecond: Number(progress.bytesPerSecond || 0),
    }))
    autoUpdater.on("update-downloaded", async () => {
      notify({ status: "ready" })
      const result = await dialog.showMessageBox({ type: "info", title: "更新已下载完成", message: "现在重启即可使用新版本。", detail: "如果暂不重启，下一次退出 PaperSage 时会自动完成更新。", buttons: ["立即重启", "退出时更新"], defaultId: 0, cancelId: 1 })
      if (result.response === 0) autoUpdater.quitAndInstall()
    })
  }

  const checkForUpdates = async () => {
    if (!supported || checking) return {
      supported,
      status: "unsupported",
      reason: unsupportedUpdateReason({ isPackaged: app.isPackaged, platform, appImage }),
    }
    checking = true
    try {
      const result = await autoUpdater.checkForUpdates()
      const version = String(result?.updateInfo?.version || "")
      return { supported, status: version && version !== app.getVersion() ? "available" : "up-to-date", version: version || undefined }
    } catch (error) {
      reportError(error)
      return { supported, status: "failed" }
    } finally { checking = false }
  }

  return { checkForUpdates, scheduleCheck: () => { if (supported) setTimeout(() => { void checkForUpdates() }, 12_000) } }
}

module.exports = { createUpdateService, supportsAutomaticUpdates, unsupportedUpdateReason }
