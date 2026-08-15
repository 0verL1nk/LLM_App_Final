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
