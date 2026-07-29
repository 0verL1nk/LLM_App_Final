const { spawn } = require("node:child_process")
const path = require("node:path")

const webRoot = path.resolve(__dirname, "..")
const npm = process.platform === "win32" ? "npm.cmd" : "npm"
const npx = process.platform === "win32" ? "npx.cmd" : "npx"
const vite = spawn(npm, ["run", "dev"], { cwd: webRoot, stdio: "inherit" })
const electron = spawn(npx, ["electron", "electron/main.cjs"], { cwd: webRoot, stdio: "inherit", env: { ...process.env, PAPERSAGE_ELECTRON_DEV: "1" } })

function stop(process) {
  if (!process.killed) process.kill()
}

electron.on("exit", () => stop(vite))
vite.on("exit", (code) => { if (code) stop(electron) })
