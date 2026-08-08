const { spawnSync } = require("node:child_process")
const fs = require("node:fs")
const path = require("node:path")

const root = path.resolve(__dirname, "..", "..")
const output = path.join(root, "web", ".desktop-backend")
fs.rmSync(output, { recursive: true, force: true })
const python = process.platform === "win32" ? "uv.exe" : "uv"
const separator = process.platform === "win32" ? ";" : ":"
const args = [
  "run", "--with", "pyinstaller", "pyinstaller", "--noconfirm", "--clean", "--onedir",
  "--name", "papersage-api", "--distpath", output,
  "--workpath", path.join(root, "web", ".pyinstaller-work"),
  "--specpath", path.join(root, "web", ".pyinstaller-work"),
  "--add-data", `${path.join(root, "web", "dist")}${separator}web/dist`,
  "--collect-data", "paddleocr", "--collect-data", "paddlex",
  "--copy-metadata", "paddleocr", "--copy-metadata", "paddlex",
  path.join(root, "scripts", "desktop_api.py"),
]
const result = spawnSync(python, args, { cwd: root, stdio: "inherit" })
process.exit(result.status ?? 1)
