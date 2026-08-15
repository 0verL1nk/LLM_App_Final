/**
 * @typedef {"cpu-active" | "downloading" | "extracting" | "gpu-active" | "error"} GpuPackPhase
 * @typedef {{ phase: GpuPackPhase, percent?: number, received?: number, total?: number, error?: string }} GpuPackStatus
 */

const fs = require("node:fs")
const path = require("node:path")

const BACKUP_DIR = "onnxruntime.cpu-backup"

/** @param {string} internalDir */
function isGpuPackApplied(internalDir) {
  return fs.existsSync(path.join(internalDir, "nvidia"))
}

/**
 * Swap the CPU onnxruntime tree for the CUDA one from the downloaded pack.
 * The runtime hook baked into every bundle puts the nvidia bin directories
 * on the DLL search path, so no bootloader change is needed.
 * @param {string} internalDir
 * @param {string} stagingDir
 */
function applyPack(internalDir, stagingDir) {
  const stagedOnnxruntime = path.join(stagingDir, "onnxruntime")
  const stagedNvidia = path.join(stagingDir, "nvidia")
  if (!fs.existsSync(stagedOnnxruntime) || !fs.existsSync(stagedNvidia)) {
    throw new Error("GPU 加速包内容不完整，请稍后重试。")
  }
  const backup = path.join(internalDir, BACKUP_DIR)
  if (!fs.existsSync(backup)) {
    fs.renameSync(path.join(internalDir, "onnxruntime"), backup)
  }
  fs.rmSync(path.join(internalDir, "onnxruntime"), { recursive: true, force: true })
  fs.renameSync(stagedOnnxruntime, path.join(internalDir, "onnxruntime"))
  fs.renameSync(stagedNvidia, path.join(internalDir, "nvidia"))
}

/**
 * @param {{ internalDir: string, workDir: string, download: (url: string, destination: string, onProgress: (received: number, total: number) => void) => Promise<void>, extract: (zipPath: string, destination: string) => Promise<void>, report?: (status: GpuPackStatus) => void, logger?: Pick<Console, "error"> }} dependencies
 * @returns {{ enable: (packUrl: string) => Promise<void>, disable: () => boolean, status: () => GpuPackStatus }}
 */
function createGpuPackService({ internalDir, workDir, download, extract, report = () => undefined, logger = console }) {
  let phase = isGpuPackApplied(internalDir) ? "gpu-active" : "cpu-active"
  const setPhase = (next, extra = {}) => {
    phase = next
    report({ phase, ...extra })
  }

  const enable = async (packUrl) => {
    if (phase === "downloading" || phase === "extracting" || phase === "gpu-active") return
    const zipPath = path.join(workDir, "gpu-pack.zip")
    const stagingDir = path.join(workDir, "staging")
    try {
      fs.mkdirSync(workDir, { recursive: true })
      setPhase("downloading")
      await download(packUrl, zipPath, (received, total) =>
        report({
          phase: "downloading",
          received,
          total,
          percent: total ? Math.floor((received / total) * 100) : undefined,
        }),
      )
      setPhase("extracting")
      fs.rmSync(stagingDir, { recursive: true, force: true })
      await extract(zipPath, stagingDir)
      applyPack(internalDir, stagingDir)
      fs.rmSync(stagingDir, { recursive: true, force: true })
      fs.rmSync(zipPath, { force: true })
      setPhase("gpu-active")
    } catch (error) {
      logger.error("PaperSage GPU pack installation failed", error)
      setPhase("error", { error: error instanceof Error ? error.message : String(error) })
    }
  }

  const disable = () => {
    try {
      const backup = path.join(internalDir, BACKUP_DIR)
      if (!fs.existsSync(backup)) {
        throw new Error("未找到 CPU 版备份，无法还原；请重新安装 PaperSage。")
      }
      fs.rmSync(path.join(internalDir, "onnxruntime"), { recursive: true, force: true })
      fs.rmSync(path.join(internalDir, "nvidia"), { recursive: true, force: true })
      fs.renameSync(backup, path.join(internalDir, "onnxruntime"))
      setPhase("cpu-active")
      return true
    } catch (error) {
      logger.error("PaperSage GPU pack removal failed", error)
      setPhase("error", { error: error instanceof Error ? error.message : String(error) })
      return false
    }
  }

  return { enable, disable, status: () => ({ phase }) }
}

module.exports = { BACKUP_DIR, applyPack, createGpuPackService, isGpuPackApplied }
