const test = require("node:test")
const assert = require("node:assert/strict")
const { supportsAutomaticUpdates } = require("./updater.cjs")

test("automatic updates require a packaged supported target", () => {
  assert.equal(supportsAutomaticUpdates({ isPackaged: false, platform: "win32" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "win32" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "darwin" }), true)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux" }), false)
  assert.equal(supportsAutomaticUpdates({ isPackaged: true, platform: "linux", appImage: "/tmp/PaperSage.AppImage" }), true)
})
