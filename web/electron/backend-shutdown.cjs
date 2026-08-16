/**
 * Backend process-tree shutdown.
 *
 * A plain child.kill() only terminates the launcher process; the packaged
 * backend spawns grandchildren (OCR workers) that survive the app, keep the
 * API port bound, and outlive "exit" for the user. On Windows the reliable
 * way is taskkill /T; elsewhere child.kill() delivers SIGTERM and Python
 * shuts down gracefully.
 *
 * @param {import("node:child_process").ChildProcess | undefined} child
 * @param {{ platform?: NodeJS.Platform, spawnKill?: (command: string, args: string[]) => void, kill?: (child: import("node:child_process").ChildProcess) => void }} [options]
 */
function shutdownBackendTree(child, options = {}) {
  const { platform = process.platform, spawnKill = defaultSpawnKill, kill = defaultKill } = options
  if (!child || child.killed || child.pid == null) return false
  if (platform === "win32") {
    spawnKill("taskkill", ["/pid", String(child.pid), "/T", "/F"])
    return true
  }
  try {
    kill(child)
  } catch {
    // The child already exited between the check and the signal.
  }
  return true
}

function defaultSpawnKill(command, args) {
  const { spawn } = require("node:child_process")
  spawn(command, args, { stdio: "ignore", windowsHide: true })
}

function defaultKill(child) {
  child.kill()
}

module.exports = { shutdownBackendTree }
