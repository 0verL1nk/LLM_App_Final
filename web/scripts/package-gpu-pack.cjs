// Builds the downloadable GPU acceleration pack: the CUDA onnxruntime tree
// plus the NVIDIA DLL tree from a GPU package build, zipped so the desktop
// app can extract both straight into the packaged backend's _internal
// directory. Requires web/dist (pnpm run build) to exist.
const { spawnSync } = require("node:child_process")
const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..", "..")
const webDir = path.resolve(__dirname, "..")
const version = require(path.join(webDir, "package.json")).version
const releaseDir = path.join(webDir, "release")
const packPath = path.join(releaseDir, `PaperSage-GPU-Pack-${version}.zip`)
const internal = path.join(webDir, ".desktop-backend", "papersage-api", "_internal")

const packageBackend = spawnSync("node", [path.join(webDir, "scripts", "package-backend.cjs")], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PAPERSAGE_DESKTOP_GPU: "1" },
})
if (packageBackend.status !== 0) process.exit(packageBackend.status ?? 1)

for (const required of [path.join(internal, "onnxruntime"), path.join(internal, "nvidia")]) {
  if (!fs.existsSync(required)) {
    process.stderr.write(`GPU bundle is missing ${required}; the pack would be incomplete.\n`)
    process.exit(1)
  }
}
fs.mkdirSync(releaseDir, { recursive: true })
fs.rmSync(packPath, { force: true })
const zip = spawnSync(
  "powershell",
  [
    "-NoProfile",
    "-Command",
    `Compress-Archive -Path "${path.join(internal, "onnxruntime")}", "${path.join(internal, "nvidia")}" -DestinationPath "${packPath}" -CompressionLevel Optimal`,
  ],
  { stdio: "inherit" },
)
if (zip.status !== 0) process.exit(zip.status ?? 1)
process.stdout.write(`GPU pack written: ${packPath}\n`)
