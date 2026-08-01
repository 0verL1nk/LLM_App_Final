/**
 * @typedef {{ isPackaged: boolean, getVersion: () => string }} ElectronApp
 * @typedef {{ showMessageBox: (options: object) => Promise<{ response: number }> }} ElectronDialog
 * @typedef {{ checkForUpdates: () => Promise<unknown>, downloadUpdate: () => Promise<unknown>, quitAndInstall: () => void, on: (event: string, listener: (...args: unknown[]) => void) => void, autoDownload: boolean, autoInstallOnAppQuit: boolean }} ElectronUpdater
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

/**
 * @param {{ app: ElectronApp, autoUpdater: ElectronUpdater, dialog: ElectronDialog, logger?: Pick<Console, "error">, platform?: NodeJS.Platform, appImage?: string }} dependencies
 * @returns {{ checkForUpdates: () => Promise<{ supported: boolean, status: "unsupported" | "up-to-date" | "available" | "failed", version?: string }>, scheduleCheck: () => void }}
 */
function createUpdateService({ app, autoUpdater, dialog, logger = console, platform = process.platform, appImage = process.env.APPIMAGE }) {
  const supported = supportsAutomaticUpdates({ isPackaged: app.isPackaged, platform, appImage })
  let checking = false
  const reportError = (error) => logger.error("PaperSage update check failed", error)
  const download = () => autoUpdater.downloadUpdate().catch(reportError)

  if (supported) {
    autoUpdater.autoDownload = false
    autoUpdater.autoInstallOnAppQuit = false
    autoUpdater.on("error", reportError)
    autoUpdater.on("update-available", async (info) => {
      const result = await dialog.showMessageBox({ type: "info", title: "有可用更新", message: `PaperSage ${info.version} 已可下载。`, detail: "下载完成后，你可以选择立即重启安装。", buttons: ["下载更新", "稍后"], defaultId: 0, cancelId: 1 })
      if (result.response === 0) download()
    })
    autoUpdater.on("update-downloaded", async () => {
      const result = await dialog.showMessageBox({ type: "info", title: "更新已准备就绪", message: "重启 PaperSage 后即可完成更新。", buttons: ["立即重启", "下次启动时安装"], defaultId: 0, cancelId: 1 })
      if (result.response === 0) autoUpdater.quitAndInstall()
    })
  }

  const checkForUpdates = async () => {
    if (!supported || checking) return { supported, status: "unsupported" }
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

module.exports = { createUpdateService, supportsAutomaticUpdates }
