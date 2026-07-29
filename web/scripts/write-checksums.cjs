const crypto = require("node:crypto")
const fs = require("node:fs")
const path = require("node:path")

const releaseDirectory = path.resolve(__dirname, "..", "release")
const packageExtensions = new Set([".exe", ".dmg", ".zip", ".appimage", ".deb"])
const files = fs.readdirSync(releaseDirectory)
  .filter((name) => packageExtensions.has(path.extname(name).toLowerCase()))
  .sort()

if (!files.length) throw new Error("No desktop packages found in web/release")

const checksums = files.map((name) => {
  const bytes = fs.readFileSync(path.join(releaseDirectory, name))
  return `${crypto.createHash("sha256").update(bytes).digest("hex")}  ${name}`
})
fs.writeFileSync(path.join(releaseDirectory, "SHA256SUMS.txt"), `${checksums.join("\n")}\n`)
