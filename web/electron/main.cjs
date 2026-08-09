const { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, shell, Tray } = require("electron")
const { autoUpdater } = require("electron-updater")
const { spawn } = require("node:child_process")
const net = require("node:net")
const path = require("node:path")
const fs = require("node:fs")
const { createUpdateService } = require("./updater.cjs")
const { createTrayService } = require("./tray.cjs")

const apiPort = Number(process.env.PAPERSAGE_DESKTOP_PORT || 18765)
let backend
let logDirectory
let mainWindow
let trayService

function getLogDirectory() {
  if (logDirectory) return logDirectory
  const installationDirectory = app.isPackaged
    ? path.dirname(process.execPath)
    : path.resolve(__dirname, "..", "..")
  const preferredDirectory = path.join(installationDirectory, "logs")
  try {
    fs.mkdirSync(preferredDirectory, { recursive: true })
    fs.accessSync(preferredDirectory, fs.constants.W_OK)
    logDirectory = preferredDirectory
  } catch {
    // Per-machine installations can be read-only. Retain diagnostics if so.
    logDirectory = app.getPath("logs")
    fs.mkdirSync(logDirectory, { recursive: true })
  }
  return logDirectory
}

function writeDesktopLog(fileName, message) {
  try {
    const logPath = path.join(getLogDirectory(), fileName)
    const maxBytes = 5 * 1024 * 1024
    if (fs.existsSync(logPath) && fs.statSync(logPath).size >= maxBytes) {
      fs.rmSync(`${logPath}.1`, { force: true })
      fs.renameSync(logPath, `${logPath}.1`)
    }
    fs.appendFileSync(logPath, `${new Date().toISOString()} | ${message}\n`, "utf8")
  } catch (error) {
    console.error("无法写入 PaperSage 诊断日志", error)
  }
}

function errorMessage(error) {
  return error instanceof Error ? (error.stack || error.message) : String(error)
}

function reportMainError(context, error) {
  const message = `${context}: ${errorMessage(error)}`
  console.error(message)
  writeDesktopLog("main.log", message)
}

const updates = createUpdateService({
  app,
  autoUpdater,
  dialog,
  logger: { error: (message, error) => reportMainError(message, error) },
  notify: (status) => BrowserWindow.getAllWindows().forEach((window) => window.webContents.send("updates:status", status)),
})

function waitForPort(port, timeoutMs = 30000) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    const probe = () => {
      const socket = net.connect({ host: "127.0.0.1", port })
      socket.once("connect", () => { socket.end(); resolve() })
      socket.once("error", () => {
        socket.destroy()
        if (Date.now() - startedAt >= timeoutMs) reject(new Error("PaperSage 服务启动超时"))
        else setTimeout(probe, 250)
      })
    }
    probe()
  })
}

function startBackend() {
  const isPackaged = app.isPackaged
  const backendExecutable = process.platform === "win32" ? "papersage-api.exe" : "papersage-api"
  const command = isPackaged
    ? path.join(process.resourcesPath, "backend", "papersage-api", backendExecutable)
    : process.platform === "win32" ? "uv.exe" : "uv"
  const args = isPackaged ? [] : ["run", "python", "-m", "api.main"]
  if (isPackaged && !fs.existsSync(command)) throw new Error(`未找到内置服务：${command}`)
  backend = spawn(command, args, {
    cwd: isPackaged ? app.getPath("userData") : path.resolve(__dirname, "..", ".."),
    windowsHide: true,
    env: {
      ...process.env,
      APP_LOG_FILE: path.join(getLogDirectory(), "backend.log"),
      APP_LOG_LEVEL: "DEBUG",
      PAPERSAGE_PORT: String(apiPort),
      PAPERSAGE_DESKTOP: "1",
    },
    stdio: "pipe",
  })
  backend.stdout.on("data", (buffer) => writeDesktopLog("backend-process.log", buffer.toString().trimEnd()))
  backend.stderr.on("data", (buffer) => {
    const message = buffer.toString().trimEnd()
    console.error(`[PaperSage API] ${message}`)
    writeDesktopLog("backend-process.log", message)
  })
  backend.on("error", (error) => reportMainError("无法启动 PaperSage 服务", error))
  backend.on("exit", (code, signal) => writeDesktopLog("main.log", `内置服务已退出：code=${code ?? "-"} signal=${signal ?? "-"}`))
}

async function createWindow() {
  startBackend()
  await waitForPort(apiPort)
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 960,
    minHeight: 680,
    show: false,
    frame: false,
    backgroundColor: "#09090b",
    titleBarStyle: "hidden",
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false },
  })
  mainWindow = window
  window.on("close", (event) => {
    if (trayService && !trayService.isQuitting()) {
      event.preventDefault()
      window.hide()
    }
  })
  window.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    if (level >= 2) writeDesktopLog("renderer.log", `${sourceId}:${line} | ${message}`)
  })
  window.webContents.on("render-process-gone", (_event, details) => {
    writeDesktopLog("main.log", `渲染进程异常退出：reason=${details.reason} exitCode=${details.exitCode}`)
  })
  window.once("ready-to-show", () => window.show())
  const frontendPort = Number(process.env.PAPERSAGE_ELECTRON_DEV ? 5173 : apiPort)
  await waitForPort(frontendPort)
  await window.loadURL(`http://127.0.0.1:${frontendPort}`)
}

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

ipcMain.handle("window:minimize", (event) => BrowserWindow.fromWebContents(event.sender)?.minimize())
ipcMain.handle("window:toggle-maximize", (event) => {
  const window = BrowserWindow.fromWebContents(event.sender)
  if (!window) return false
  if (window.isMaximized()) window.unmaximize()
  else window.maximize()
  return window.isMaximized()
})
ipcMain.handle("window:close", (event) => BrowserWindow.fromWebContents(event.sender)?.close())
ipcMain.handle("updates:check", () => updates.checkForUpdates())
ipcMain.handle("logs:open", async () => shell.openPath(getLogDirectory()))

process.on("uncaughtException", (error) => reportMainError("桌面应用发生未捕获错误", error))
process.on("unhandledRejection", (reason) => reportMainError("桌面应用发生未处理异常", reason))

app.whenReady().then(async () => {
  trayService = createTrayService({
    Tray,
    Menu,
    nativeImage,
    app,
    iconPath: path.join(__dirname, "tray-icon.svg"),
    showWindow: showMainWindow,
  })
  await createWindow()
  updates.scheduleCheck()
}).catch((error) => {
  reportMainError("桌面应用无法启动", error)
  dialog.showErrorBox("PaperSage 无法启动", "应用启动失败。请在安装目录的 logs 文件夹中查看 main.log。")
  app.quit()
})
app.on("window-all-closed", () => { if (process.platform !== "darwin" && (!trayService || trayService.isQuitting())) app.quit() })
app.on("activate", showMainWindow)
app.on("before-quit", () => {
  trayService?.beginQuit()
  if (backend && !backend.killed) backend.kill()
})
