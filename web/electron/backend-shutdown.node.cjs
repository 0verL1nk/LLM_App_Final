const test = require("node:test")
const assert = require("node:assert/strict")

const { shutdownBackendTree } = require("./backend-shutdown.cjs")

function fakeChild({ pid = 4242, killed = false } = {}) {
  return { pid, killed, killCalls: 0, get killed_() { return killed }, kill() { this.killCalls += 1 } }
}

test("kills the whole tree with taskkill on Windows", () => {
  const calls = []
  const child = fakeChild()
  const handled = shutdownBackendTree(child, {
    platform: "win32",
    spawnKill: (command, args) => calls.push([command, args]),
    kill: () => assert.fail("taskkill path must not call child.kill()"),
  })
  assert.equal(handled, true)
  assert.deepEqual(calls, [["taskkill", ["/pid", "4242", "/T", "/F"]]])
  assert.equal(child.killCalls, 0)
})

test("signals the launcher directly on other platforms", () => {
  const child = fakeChild({ pid: 17 })
  shutdownBackendTree(child, {
    platform: "linux",
    spawnKill: () => assert.fail("linux path must not spawn taskkill"),
    kill: (candidate) => candidate.kill(),
  })
  assert.equal(child.killCalls, 1)
})

test("ignores missing or already-dead children without throwing", () => {
  assert.equal(shutdownBackendTree(undefined, { platform: "win32", spawnKill: () => {} }), false)
  assert.equal(
    shutdownBackendTree(fakeChild({ killed: true }), { platform: "win32", spawnKill: () => {} }),
    false,
  )
  const pidless = fakeChild()
  pidless.pid = undefined
  assert.equal(shutdownBackendTree(pidless, { platform: "linux", kill: () => {} }), false)
})
