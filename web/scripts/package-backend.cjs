const { spawnSync } = require("node:child_process")
const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..", "..")
const output = path.join(root, "web", ".desktop-backend")
fs.rmSync(output, { recursive: true, force: true })
const python = process.platform === "win32" ? "uv.exe" : "uv"
const separator = process.platform === "win32" ? ";" : ":"
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
const args = [
  "run", "--with", "pyinstaller", "pyinstaller", "--noconfirm", "--clean", "--onedir",
  "--name", "papersage-api", "--distpath", output,
  "--workpath", path.join(root, "web", ".pyinstaller-work"),
  "--specpath", path.join(root, "web", ".pyinstaller-work"),
  "--add-data", `${path.join(root, "web", "dist")}${separator}web/dist`,
  "--collect-data", "paddlex", "--collect-binaries", "paddle",
  path.join(root, "scripts", "desktop_api.py"),
]
for (const packageName of ocrMetadataPackages) args.splice(-1, 0, "--copy-metadata", packageName)
const result = spawnSync(python, args, { cwd: root, stdio: "inherit" })
process.exit(result.status ?? 1)
