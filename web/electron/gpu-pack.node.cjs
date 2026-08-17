const assert = require("node:assert/strict")
const fs = require("node:fs")
const os = require("node:os")
const path = require("node:path")
const test = require("node:test")

const { BACKUP_DIR, createGpuPackService } = require("./gpu-pack.cjs")

function makeSandbox() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "papersage-gpu-pack-"))
  const internalDir = path.join(root, "internal")
  const workDir = path.join(root, "work")
  const cpuMarker = path.join(internalDir, "onnxruntime", "cpu.txt")
  fs.mkdirSync(path.dirname(cpuMarker), { recursive: true })
  fs.writeFileSync(cpuMarker, "cpu", "utf8")
  return { root, internalDir, workDir, cpuMarker }
}

function fakeExtract(stagingDir) {
  fs.mkdirSync(path.join(stagingDir, "onnxruntime"), { recursive: true })
  fs.mkdirSync(path.join(stagingDir, "nvidia", "cudnn", "bin"), { recursive: true })
  fs.writeFileSync(path.join(stagingDir, "onnxruntime", "gpu.txt"), "gpu", "utf8")
  fs.writeFileSync(path.join(stagingDir, "nvidia", "cudnn", "bin", "cudnn64_9.dll"), "dll", "utf8")
}

test("enable swaps the onnxruntime tree and keeps a CPU backup", async () => {
  const sandbox = makeSandbox()
  const statuses = []
  const service = createGpuPackService({
    internalDir: sandbox.internalDir,
    workDir: sandbox.workDir,
    download: async (_url, destination) => fs.writeFileSync(destination, "zip", "utf8"),
    extract: async (_zipPath, stagingDir) => fakeExtract(stagingDir),
    report: (status) => statuses.push(status),
    logger: { error: () => undefined },
  })

  assert.equal(service.status().phase, "cpu-active")
  await service.enable("https://example.invalid/pack.zip")

  assert.equal(service.status().phase, "gpu-active")
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, "nvidia", "cudnn", "bin", "cudnn64_9.dll")))
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, "onnxruntime", "gpu.txt")))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, "onnxruntime", "cpu.txt")))
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, BACKUP_DIR, "cpu.txt")))
  assert.ok(statuses.some((status) => status.phase === "downloading"))
  fs.rmSync(sandbox.root, { recursive: true, force: true })
})

test("disable restores the CPU tree and removes the NVIDIA tree", async () => {
  const sandbox = makeSandbox()
  const service = createGpuPackService({
    internalDir: sandbox.internalDir,
    workDir: sandbox.workDir,
    download: async (_url, destination) => fs.writeFileSync(destination, "zip", "utf8"),
    extract: async (_zipPath, stagingDir) => fakeExtract(stagingDir),
    logger: { error: () => undefined },
  })
  await service.enable("https://example.invalid/pack.zip")

  assert.equal(service.disable(), true)

  assert.equal(service.status().phase, "cpu-active")
  assert.ok(fs.existsSync(sandbox.cpuMarker))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, "nvidia")))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, BACKUP_DIR)))
  fs.rmSync(sandbox.root, { recursive: true, force: true })
})

test("an incomplete pack fails without touching the CPU tree", async () => {
  const sandbox = makeSandbox()
  const service = createGpuPackService({
    internalDir: sandbox.internalDir,
    workDir: sandbox.workDir,
    download: async (_url, destination) => fs.writeFileSync(destination, "zip", "utf8"),
    extract: async (_zipPath, stagingDir) => fs.mkdirSync(stagingDir, { recursive: true }),
    logger: { error: () => undefined },
  })

  await service.enable("https://example.invalid/pack.zip")

  assert.equal(service.status().phase, "error")
  assert.ok(fs.existsSync(sandbox.cpuMarker))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, BACKUP_DIR)))
  fs.rmSync(sandbox.root, { recursive: true, force: true })
})

test("enable falls back to copy+delete when staging crosses drives (EXDEV)", async (t) => {
  const { mock } = require("node:test")
  const sandbox = makeSandbox()
  t.after(() => {
    mock.restoreAll()
    fs.rmSync(sandbox.root, { recursive: true, force: true })
  })
  // Only moves out of the staging tree are cross-volume; renames inside the
  // internal tree (the backup) keep working, as they do on a real machine.
  const originalRename = fs.renameSync
  mock.method(fs, "renameSync", (source, destination) => {
    if (source.startsWith(sandbox.workDir)) {
      throw Object.assign(new Error("cross-device link not permitted"), { code: "EXDEV" })
    }
    originalRename(source, destination)
  })
  const service = createGpuPackService({
    internalDir: sandbox.internalDir,
    workDir: sandbox.workDir,
    download: async (_url, destination) => fs.writeFileSync(destination, "zip", "utf8"),
    extract: async (_zipPath, stagingDir) => fakeExtract(stagingDir),
    report: () => undefined,
    logger: { error: () => undefined },
  })

  await service.enable("https://example.invalid/pack.zip")

  assert.equal(service.status().phase, "gpu-active")
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, "onnxruntime", "gpu.txt")))
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, "nvidia", "cudnn", "bin", "cudnn64_9.dll")))
  assert.ok(fs.existsSync(path.join(sandbox.internalDir, BACKUP_DIR, "cpu.txt")))
  assert.ok(!fs.existsSync(path.join(sandbox.workDir, "staging", "onnxruntime")))
})

test("enable rolls the CPU tree back when the swap dies mid-flight", async (t) => {
  const { mock } = require("node:test")
  const sandbox = makeSandbox()
  const errors = []
  t.after(() => {
    mock.restoreAll()
    fs.rmSync(sandbox.root, { recursive: true, force: true })
  })
  // Cross-volume staging forces the copy path, and the onnxruntime copy (the
  // first cpSync of the swap) fails; the internal tree must roll back to CPU.
  const originalRename = fs.renameSync
  mock.method(fs, "renameSync", (source, destination) => {
    if (source.startsWith(sandbox.workDir)) {
      throw Object.assign(new Error("cross-device link not permitted"), { code: "EXDEV" })
    }
    originalRename(source, destination)
  })
  mock.method(fs, "cpSync", () => {
    throw new Error("disk full")
  })
  const service = createGpuPackService({
    internalDir: sandbox.internalDir,
    workDir: sandbox.workDir,
    download: async (_url, destination) => fs.writeFileSync(destination, "zip", "utf8"),
    extract: async (_zipPath, stagingDir) => fakeExtract(stagingDir),
    report: () => undefined,
    logger: { error: (_message, error) => errors.push(error) },
  })

  await service.enable("https://example.invalid/pack.zip")

  assert.equal(service.status().phase, "error")
  assert.ok(fs.existsSync(sandbox.cpuMarker))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, BACKUP_DIR)))
  assert.ok(!fs.existsSync(path.join(sandbox.internalDir, "nvidia")))
  assert.ok(errors.length >= 1)
})
