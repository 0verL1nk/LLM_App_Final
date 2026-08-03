const { app, BrowserWindow, dialog, ipcMain } = require("electron")
const { autoUpdater } = require("electron-updater")
const { spawn } = require("node:child_process")
const net = require("node:net")
const path = require("node:path")
const fs = require("node:fs")
const { createUpdateService } = require("./updater.cjs")

const apiPort = Number(process.env.PAPERSAGE_DESKTOP_PORT || 18765)
let backend
const updates = createUpdateService({
  app,
  autoUpdater,
  dialog,
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
    env: { ...process.env, PAPERSAGE_PORT: String(apiPort), PAPERSAGE_DESKTOP: "1" },
    stdio: "pipe",
  })
  backend.stderr.on("data", (buffer) => console.error(`[PaperSage API] ${buffer}`))
  backend.on("error", (error) => console.error("无法启动 PaperSage 服务", error))
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
  window.once("ready-to-show", () => window.show())
  const frontendPort = Number(process.env.PAPERSAGE_ELECTRON_DEV ? 5173 : apiPort)
  await waitForPort(frontendPort)
  await window.loadURL(`http://127.0.0.1:${frontendPort}`)
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

app.whenReady().then(async () => {
  await createWindow()
  updates.scheduleCheck()
}).catch((error) => { console.error(error); app.quit() })
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit() })
app.on("before-quit", () => { if (backend && !backend.killed) backend.kill() })
