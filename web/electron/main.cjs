const { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, Notification, shell, Tray } = require("electron")
const { autoUpdater } = require("electron-updater")
const { spawn } = require("node:child_process")
const net = require("node:net")
const path = require("node:path")
const fs = require("node:fs")
const { createUpdateService } = require("./updater.cjs")
const { createTrayService } = require("./tray.cjs")
const { createGpuPackService } = require("./gpu-pack.cjs")
const { acquireSingleInstanceLockWithRetry } = require("./instance-lock.cjs")

const apiPort = Number(process.env.PAPERSAGE_DESKTOP_PORT || 18765)
let backend
let logDirectory
let modelsDirectory
let mainWindow
let trayService

// Updates and long migrations leave a window of seconds where no window
// exists yet; without the lock a second impatient launch races the first.
// quitAndInstall also relaunches while the previous instance may still be
// tearing down its tray and backend, so retry the lock briefly instead of
// quitting in silence — a silent quit reads as "the update broke the app".
acquireSingleInstanceLockWithRetry({
  requestLock: () => app.requestSingleInstanceLock(),
  log: (message) => writeDesktopLog("main.log", message),
  quit: () => app.quit(),
  onAcquired: startWhenReady,
})
app.on("second-instance", () => showMainWindow())

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

function getModelsDirectory() {
  if (modelsDirectory) return modelsDirectory
  const installationDirectory = app.isPackaged
    ? path.dirname(process.execPath)
    : path.resolve(__dirname, "..", "..")
  const preferredDirectory = path.join(installationDirectory, "models")
  try {
    fs.mkdirSync(preferredDirectory, { recursive: true })
    fs.accessSync(preferredDirectory, fs.constants.W_OK)
    modelsDirectory = preferredDirectory
  } catch {
    // Per-machine installations can be read-only. Model downloads must stay
    // possible, so fall back to the user profile like the logs do.
    modelsDirectory = path.join(app.getPath("userData"), "models")
    fs.mkdirSync(modelsDirectory, { recursive: true })
  }
  return modelsDirectory
}

function migrateLegacyModelCache() {
  // Releases before the install-directory cache kept OCR models under
  // <userData>/.cache/paddleocr. Copy them forward once so an upgrade does
  // not force a fresh model download on a weak network.
  const legacyCache = path.join(app.getPath("userData"), ".cache", "paddleocr")
  const targetCache = path.join(getModelsDirectory(), "paddleocr")
  try {
    if (fs.existsSync(legacyCache) && !fs.existsSync(targetCache)) {
      fs.cpSync(legacyCache, targetCache, { recursive: true })
      writeDesktopLog("main.log", "已迁移历史 OCR 模型缓存到 models 目录")
    }
  } catch (error) {
    writeDesktopLog("main.log", `迁移历史 OCR 模型缓存失败：${errorMessage(error)}`)
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
  logger: { error: (message, error) => reportMainError(message, error) },
  notify: (status) => BrowserWindow.getAllWindows().forEach((window) => window.webContents.send("updates:status", status)),
  notifySystem: () => {
    if (!Notification.isSupported()) return
    new Notification({ title: "PaperSage", body: "更新已就绪,正在重启应用,请稍候……" }).show()
  },
})

function waitForPort(port, timeoutMs = 30000, childProcess) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    // A dead backend will never bind the port; surface its exit instead of
    // letting the user stare at the splash until the timeout.
    let rejected = false
    const onExit = (code, signal) => {
      rejected = true
      reject(new Error(`PaperSage 服务意外退出：code=${code ?? "-"} signal=${signal ?? "-"}`))
    }
    if (childProcess) childProcess.once("exit", onExit)
    const finish = (action) => {
      if (childProcess) childProcess.removeListener("exit", onExit)
      action()
    }
    const probe = () => {
      if (rejected) return
      const socket = net.connect({ host: "127.0.0.1", port })
      socket.once("connect", () => { socket.end(); finish(resolve) })
      socket.once("error", () => {
        socket.destroy()
        if (rejected) return
        if (Date.now() - startedAt >= timeoutMs) finish(() => reject(new Error("PaperSage 服务启动超时")))
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
  if (isPackaged) migrateLegacyModelCache()
  const backendEnv = {
    ...process.env,
    // Piped stdio on Windows defaults to the ANSI codepage, which garbles
    // Chinese log lines when decoded as UTF-8 below.
    PYTHONUTF8: "1",
    APP_LOG_FILE: path.join(getLogDirectory(), "backend.log"),
    APP_LOG_LEVEL: "DEBUG",
    PAPERSAGE_PORT: String(apiPort),
    PAPERSAGE_DESKTOP: "1",
  }
  if (isPackaged) backendEnv.LOCAL_MODELS_ROOT = getModelsDirectory()
  backend = spawn(command, args, {
    cwd: isPackaged ? app.getPath("userData") : path.resolve(__dirname, "..", ".."),
    windowsHide: true,
    env: backendEnv,
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
  // Show the splash before the port wait: post-update launches can spend
  // tens of seconds in migrations while the backend port stays closed, and
  // an invisible app invites a second launch.
  await window.loadFile(path.join(__dirname, "splash.html"))
  await waitForPort(apiPort, 120_000, backend)
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
ipcMain.handle("updates:install", () => updates.installUpdate())
ipcMain.handle("app:version", () => (app.isPackaged ? app.getVersion() : require("../package.json").version))
ipcMain.handle("app:relaunch", () => {
  app.relaunch()
  app.exit(0)
})
ipcMain.handle("logs:open", async () => shell.openPath(getLogDirectory()))

let gpuPackService
function getGpuPackService() {
  if (gpuPackService) return gpuPackService
  gpuPackService = createGpuPackService({
    internalDir: app.isPackaged
      ? path.join(process.resourcesPath, "backend", "papersage-api", "_internal")
      : path.resolve(__dirname, "..", ".desktop-backend", "papersage-api", "_internal"),
    workDir: path.join(app.getPath("userData"), "gpu-pack"),
    download: downloadWithResume,
    extract: extractZip,
    report: (status) =>
      BrowserWindow.getAllWindows().forEach((window) => window.webContents.send("gpu-pack:status", status)),
    logger: { error: (message, error) => reportMainError(message, error) },
  })
  return gpuPackService
}

function downloadWithResume(url, destination, onProgress, remainingAttempts = 5) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const alreadyReceived = fs.existsSync(destination) ? fs.statSync(destination).size : 0
      const request = net.request({
        url,
        headers: alreadyReceived ? { Range: `bytes=${alreadyReceived}-` } : {},
        redirect: "follow",
      })
      request.on("response", (response) => {
        const status = response.statusCode
        if (status !== 200 && status !== 206) {
          request.abort()
          retryOrReject(new Error(`GPU 加速包下载失败：HTTP ${status}`))
          return
        }
        const resumed = status === 206
        const contentRange = String(response.headers["content-range"] || "")
        const totalFromRange = Number(contentRange.split("/")[1] || 0)
        const total = totalFromRange || Number(response.headers["content-length"] || 0) + (resumed ? alreadyReceived : 0)
        const stream = fs.createWriteStream(destination, { flags: resumed ? "a" : "w" })
        let received = alreadyReceived
        response.on("data", (chunk) => {
          received += chunk.length
          stream.write(chunk)
          onProgress(received, total)
        })
        response.on("end", () => stream.end(resolve))
        response.on("error", (error) => {
          stream.end()
          retryOrReject(error)
        })
      })
      request.on("error", retryOrReject)
      request.end()
    }
    const retryOrReject = (error) => {
      if (remainingAttempts > 0) {
        remainingAttempts -= 1
        writeDesktopLog("main.log", `GPU 加速包下载中断，剩余重试 ${remainingAttempts} 次：${errorMessage(error)}`)
        setTimeout(attempt, 2000)
      } else {
        reject(error)
      }
    }
    attempt()
  })
}

function extractZip(zipPath, destination) {
  return new Promise((resolve, reject) => {
    const result = require("node:child_process").spawnSync(
      "powershell",
      ["-NoProfile", "-Command", `Expand-Archive -LiteralPath "${zipPath}" -DestinationPath "${destination}" -Force`],
      { stdio: "ignore" },
    )
    if (result.status === 0) resolve()
    else reject(new Error("GPU 加速包解压失败。"))
  })
}

ipcMain.handle("gpu-pack:status", () => {
  if (!app.isPackaged) return { phase: "cpu-active" }
  return getGpuPackService().status()
})
ipcMain.handle("gpu-pack:enable", async () => {
  if (!app.isPackaged) return { ok: false, phase: "cpu-active" }
  const version = app.getVersion()
  await getGpuPackService().enable(
    `https://github.com/0verL1nk/PaperSage/releases/download/v${version}/PaperSage-GPU-Pack-${version}.zip`,
  )
  const { phase } = getGpuPackService().status()
  return { ok: phase === "gpu-active", phase }
})
ipcMain.handle("gpu-pack:disable", () => {
  if (!app.isPackaged) return { ok: false }
  return { ok: getGpuPackService().disable() }
})

process.on("uncaughtException", (error) => reportMainError("桌面应用发生未捕获错误", error))
process.on("unhandledRejection", (reason) => reportMainError("桌面应用发生未处理异常", reason))

function startWhenReady() {
  app.whenReady().then(async () => {
    trayService = createTrayService({
      Tray,
      Menu,
      nativeImage,
      app,
      iconPath: path.join(__dirname, "tray-icon.png"),
      showWindow: showMainWindow,
      reportError: (message) => writeDesktopLog("main.log", message),
    })
    await createWindow()
    updates.scheduleCheck()
  }).catch((error) => {
    reportMainError("桌面应用无法启动", error)
    dialog.showErrorBox("PaperSage 无法启动", "应用启动失败。请在安装目录的 logs 文件夹中查看 main.log。")
    app.quit()
  })
}
app.on("window-all-closed", () => { if (process.platform !== "darwin" && (!trayService || trayService.isQuitting())) app.quit() })
app.on("activate", showMainWindow)
app.on("before-quit", () => {
  trayService?.beginQuit()
  if (backend && !backend.killed) backend.kill()
})
