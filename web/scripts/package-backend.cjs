const { spawnSync } = require("node:child_process")
const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..", "..")
const output = path.join(root, "web", ".desktop-backend")
fs.rmSync(output, { recursive: true, force: true })
const python = process.platform === "win32" ? "uv.exe" : "uv"
const separator = process.platform === "win32" ? ";" : ":"
// PAPERSAGE_DESKTOP_GPU=1 swaps CPU ONNX Runtime for the CUDA build so the
// packaged OCR uses NVIDIA GPUs. The CUDA/cuDNN runtime wheels add roughly
// 1-2 GB to the installer, so the default package stays CPU-only.
const gpuBundle =
  process.platform === "win32" && ["1", "true", "yes"].includes((process.env.PAPERSAGE_DESKTOP_GPU || "").toLowerCase())

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { cwd: root, encoding: "utf8", stdio: "inherit", ...options })
  if (result.status !== 0) process.exit(result.status ?? 1)
  return result
}

function listFilesRecursively(rootDir) {
  const files = []
  if (!fs.existsSync(rootDir)) return files
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const entryPath = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(entryPath)
      else files.push(entryPath)
    }
  }
  walk(rootDir)
  return files
}

// The GPU bundle must not ship both onnxruntime and onnxruntime-gpu: they
// install the same importable module and whichever wins by path order is
// undefined. fastembed declares onnxruntime as a hard dependency, so the
// pinned closure is installed with --no-deps (it is already fully resolved
// by uv export) and the CUDA runtime goes in through a separate resolve.
// The [cuda]/[cudnn] extras of onnxruntime-gpu are empty on Windows; the
// nvidia-*-cu13 wheels provide the CUDA/cuDNN DLLs instead.
function resolvePyinstallerInvocation() {
  if (!gpuBundle) {
    return { command: python, prefix: ["run", "--with", "pyinstaller", "pyinstaller"] }
  }
  const venvDir = path.join(root, "web", ".pyinstaller-gpu-venv")
  const venvPython = path.join(venvDir, "Scripts", "python.exe")
  const requirementsPath = path.join(root, "web", ".pyinstaller-gpu-requirements.txt")
  fs.rmSync(venvDir, { recursive: true, force: true })
  run(python, ["venv", venvDir])
  run(python, ["export", "--frozen", "--no-dev", "--no-hashes", "--output-file", requirementsPath])
  const lines = fs
    .readFileSync(requirementsPath, "utf8")
    .split(/\r?\n/)
    .filter((line) => line && !/^onnxruntime==/.test(line.trim()))
  // The CPU bundle bakes the onnxruntime Python wrapper into its PYZ archive,
  // so a GPU pack that swaps only the package directory is only safe when the
  // GPU runtime is the exact same version as the CPU one.
  const onnxruntimeVersion = (fs
    .readFileSync(requirementsPath, "utf8")
    .match(/^onnxruntime==(\S+)/m) || [])[1]
  if (!onnxruntimeVersion) {
    process.stderr.write("Unable to resolve the pinned onnxruntime version for the GPU bundle.\n")
    process.exit(1)
  }
  fs.writeFileSync(requirementsPath, `${lines.join("\n")}\n`)
  run(python, ["pip", "install", "--python", venvPython, "--no-deps", "-r", requirementsPath])
  // nvidia-*-cu13 metapackages are sdists that fail to build in the bare
  // venv; the real distribution names install as wheels directly.
  run(python, [
    "pip",
    "install",
    "--python",
    venvPython,
    `onnxruntime-gpu==${onnxruntimeVersion}`,
    "nvidia-cudnn-cu13",
    "nvidia-cublas",
    "nvidia-cuda-runtime",
    "nvidia-cuda-nvrtc",
    "pyinstaller",
  ])
  return { command: venvPython, prefix: ["-m", "PyInstaller"] }
}

const metadataResult = spawnSync(
  python,
  ["run", "--no-sync", "python", path.join(root, "scripts", "paddlex_ocr_pyinstaller_metadata.py")],
  { cwd: root, encoding: "utf8" },
)
if (metadataResult.status !== 0) {
  process.stderr.write(metadataResult.stderr || "Unable to resolve PaddleX OCR package metadata.\n")
  process.exit(metadataResult.status ?? 1)
}
const ocrMetadataPackages = metadataResult.stdout.split(/\r?\n/).filter(Boolean)
// langchain_community resolves fastembed via importlib.import_module, which
// PyInstaller cannot detect statically; without an explicit collect the
// packaged ingestion fails at the embedding step with "Could not import
// 'fastembed'".
const pyinstallerArgs = [
  "--noconfirm", "--clean", "--onedir",
  "--name", "papersage-api", "--distpath", output,
  "--workpath", path.join(root, "web", ".pyinstaller-work"),
  "--specpath", path.join(root, "web", ".pyinstaller-work"),
  "--add-data", `${path.join(root, "web", "dist")}${separator}web/dist`,
  "--add-data", `${path.join(root, "alembic.ini")}${separator}.`,
  "--add-data", `${path.join(root, "alembic")}${separator}alembic`,
  "--add-data", `${path.join(root, "agent", "skills")}${separator}agent/skills`,
  "--collect-data", "paddlex", "--collect-binaries", "paddle",
  // --collect-all does not copy package metadata; the dist-info directory is
  // what the post-build assertion below checks.
  "--collect-all", "fastembed", "--copy-metadata", "fastembed",
  path.join(root, "scripts", "desktop_api.py"),
]
for (const packageName of ocrMetadataPackages) pyinstallerArgs.splice(-1, 0, "--copy-metadata", packageName)
// The DLL hook ships in every bundle: it is a no-op without the nvidia tree,
// and it is what makes a GPU pack extracted into _internal work later.
pyinstallerArgs.splice(-1, 0, "--runtime-hook", path.join(root, "web", "scripts", "gpu_dll_runtime_hook.py"))
// resolvePyinstallerInvocation must run first: it creates the GPU venv whose
// NVIDIA DLLs the arguments below reference.
const invocation = resolvePyinstallerInvocation()
if (gpuBundle) {
  pyinstallerArgs.splice(-1, 0, "--copy-metadata", "onnxruntime-gpu")
  // The cu13 wheels scatter their DLLs across several trees below
  // site-packages/nvidia (cu13/bin/x86_64, cudnn/bin, ...). Gather every
  // DLL into the single directory gpu_dll_runtime_hook.py exposes to the
  // Windows loader; collecting packages does not work here because most of
  // these trees are not importable packages at all.
  const venvSitePackages = path.join(root, "web", ".pyinstaller-gpu-venv", "Lib", "site-packages")
  const nvidiaRoot = path.join(venvSitePackages, "nvidia")
  const cudaDlls = listFilesRecursively(nvidiaRoot).filter((file) => file.toLowerCase().endsWith(".dll"))
  for (const requiredDll of [/^cudnn64_\d+\.dll$/, /^cublas64_\d+\.dll$/, /^cublaslt64_\d+\.dll$/, /^cudart64_\d+\.dll$/, /^nvrtc64_[\d_]+\.dll$/]) {
    if (!cudaDlls.some((file) => requiredDll.test(path.basename(file).toLowerCase()))) {
      process.stderr.write(`GPU venv has no DLL matching ${requiredDll}; the CUDA wheels did not install.\n`)
      process.exit(1)
    }
  }
  for (const dll of cudaDlls) {
    pyinstallerArgs.splice(-1, 0, "--add-binary", `${dll}${separator}nvidia/cu13/bin/x86_64`)
  }
}
run(invocation.command, [...invocation.prefix, ...pyinstallerArgs])
// The backend runs Alembic migrations at startup; a bundle without the
// alembic tree bricks the desktop app with "No 'script_location'".
const internal = path.join(output, "papersage-api", "_internal")
for (const required of [
  path.join(internal, "alembic.ini"),
  path.join(internal, "alembic", "env.py"),
  // The use_skill tool resolves skills next to its loader module; without
  // the data directory every skill call answers "Available skills: none".
  path.join(internal, "agent", "skills", "summary", "SKILL.md"),
]) {
  if (!fs.existsSync(required)) {
    process.stderr.write(`Packaged backend is missing ${required}; migrations would fail at startup.\n`)
    process.exit(1)
  }
}
// fastembed is imported dynamically (see pyinstallerArgs), so the dist-info
// directory produced by --collect-all is the on-disk proof it was bundled.
if (!fs.readdirSync(internal).some((name) => /^fastembed-[^/]*\.dist-info$/.test(name))) {
  process.stderr.write("Packaged backend is missing fastembed; document ingestion would fail at the embedding step.\n")
  process.exit(1)
}
if (gpuBundle && !fs.readdirSync(internal).some((name) => /^onnxruntime_gpu-[^/]*\.dist-info$/.test(name))) {
  process.stderr.write("GPU bundle is missing onnxruntime-gpu; OCR would silently fall back to CPU.\n")
  process.exit(1)
}
if (gpuBundle) {
  const bundledFiles = new Set()
  const walk = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.isDirectory()) walk(path.join(directory, entry.name))
      else bundledFiles.add(entry.name.toLowerCase())
    }
  }
  walk(internal)
  for (const requiredDll of [/^cudnn64_\d+\.dll$/, /^cublas64_\d+\.dll$/, /^cublaslt64_\d+\.dll$/]) {
    if (![...bundledFiles].some((name) => requiredDll.test(name))) {
      process.stderr.write(`GPU bundle has no DLL matching ${requiredDll}; the CUDA provider would fail at startup.\n`)
      process.exit(1)
    }
  }
}
process.exit(0)
