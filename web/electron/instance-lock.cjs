/**
 * Single-instance lock acquisition with retry.
 *
 * quitAndInstall relaunches the app while the previous instance may still be
 * tearing down its tray and backend child; the OS-level lock release lags by
 * seconds. Retrying briefly lets the relaunched instance take over instead of
 * quitting silently (a silent quit reads as "the update broke the app").
 *
 * @param {{ requestLock: () => boolean, delayMs?: number, maxAttempts?: number, log: (message: string) => void, quit: () => void, onAcquired: () => void, schedule?: (callback: () => void, delayMs: number) => void }} options
 */
function acquireSingleInstanceLockWithRetry(options) {
  const {
    requestLock,
    delayMs = 500,
    maxAttempts = 20,
    log,
    quit,
    onAcquired,
    schedule = (callback, delay) => setTimeout(callback, delay),
  } = options

  if (requestLock()) {
    onAcquired()
    return
  }

  let attempts = 0
  const retry = () => {
    attempts += 1
    if (requestLock()) {
      log(`单实例锁在第 ${attempts} 次重试后获得（等待 ${(attempts * delayMs) / 1000} 秒）`)
      onAcquired()
      return
    }
    if (attempts < maxAttempts) {
      schedule(retry, delayMs)
      return
    }
    log(`另一实例持有单实例锁超过 ${(maxAttempts * delayMs) / 1000} 秒，本次启动退出`)
    quit()
  }
  schedule(retry, delayMs)
}

module.exports = { acquireSingleInstanceLockWithRetry }
