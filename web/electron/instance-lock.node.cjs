const test = require("node:test")
const assert = require("node:assert/strict")

const { acquireSingleInstanceLockWithRetry } = require("./instance-lock.cjs")

function harness({ outcomes }) {
  const state = { acquired: 0, quit: 0, logs: [], timers: [] }
  let calls = 0
  acquireSingleInstanceLockWithRetry({
    requestLock: () => outcomes[Math.min(calls++, outcomes.length - 1)],
    delayMs: 1,
    maxAttempts: 20,
    log: (message) => state.logs.push(message),
    quit: () => { state.quit += 1 },
    onAcquired: () => { state.acquired += 1 },
    schedule: (callback, delay) => state.timers.push({ callback, delay }),
  })
  return state
}

test("acquires immediately when the lock is free", () => {
  const state = harness({ outcomes: [true] })
  assert.equal(state.acquired, 1)
  assert.equal(state.quit, 0)
  assert.deepEqual(state.timers, [])
})

test("retries while the previous instance is tearing down", () => {
  const state = harness({ outcomes: [false, false, true] })
  assert.equal(state.acquired, 0, "acquisition waits for the retry")

  state.timers.shift().callback()
  assert.equal(state.acquired, 0)

  state.timers.shift().callback()
  assert.equal(state.acquired, 1)
  assert.equal(state.quit, 0)
  assert.match(state.logs[0], /第 2 次重试后获得/)
})

test("quits with a log line when the lock never frees", () => {
  const state = harness({ outcomes: [false] })
  for (let index = 0; index < 20; index += 1) {
    const timer = state.timers.shift()
    assert.ok(timer, `expected timer on attempt ${index}`)
    timer.callback()
  }
  assert.equal(state.acquired, 0)
  assert.equal(state.quit, 1)
  assert.deepEqual(state.timers, [])
  assert.match(state.logs[0], /持有单实例锁超过/)
})
