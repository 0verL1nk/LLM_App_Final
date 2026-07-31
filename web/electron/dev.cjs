const { spawn } = require("node:child_process")
const path = require("node:path")

const webRoot = path.resolve(__dirname, "..")
const pnpm = process.platform === "win32" ? "pnpm.cmd" : "pnpm"
const vite = spawn(pnpm, ["run", "dev"], { cwd: webRoot, stdio: "inherit" })
const electron = spawn(pnpm, ["exec", "electron", "electron/main.cjs"], { cwd: webRoot, stdio: "inherit", env: { ...process.env, PAPERSAGE_ELECTRON_DEV: "1" } })

function stop(process) {
  if (!process.killed) process.kill()
}

electron.on("exit", () => stop(vite))
vite.on("exit", (code) => { if (code) stop(electron) })
