const test = require("node:test")
const assert = require("node:assert/strict")
const { createTrayService } = require("./tray.cjs")

test("reports a loadable-but-empty tray icon instead of silently going invisible", () => {
  const errors = []
  createTrayService({
    Tray: class {
      setToolTip() {}
      setContextMenu() {}
      on() {}
    },
    Menu: { buildFromTemplate: (items) => items },
    nativeImage: { createFromPath: () => ({ isEmpty: () => true, setTemplateImage: () => undefined }) },
    app: { quit: () => undefined },
    iconPath: "/apps/PaperSage/resources/tray-icon.png",
    showWindow: () => undefined,
    platform: "win32",
    reportError: (message) => errors.push(message),
  })
  assert.equal(errors.length, 1)
  assert.match(errors[0], /tray-icon\.png/)
})

test("tray restores the window and exits only through its explicit quit action", () => {
  let showCount = 0
  let quitCount = 0
  let menuItems = []
  let clickListener
  const service = createTrayService({
    Tray: class {
      setToolTip() {}
      setContextMenu(menu) { menuItems = menu }
      on(event, listener) { if (event === "click") clickListener = listener }
    },
    Menu: { buildFromTemplate: (items) => items },
    nativeImage: { createFromPath: () => ({ isEmpty: () => false, setTemplateImage: () => undefined }) },
    app: { quit: () => { quitCount += 1 } },
    iconPath: "tray-icon.svg",
    showWindow: () => { showCount += 1 },
    platform: "win32",
  })

  clickListener()
  menuItems[0].click()
  menuItems[1].click()

  assert.equal(showCount, 2)
  assert.equal(quitCount, 1)
  assert.equal(service.isQuitting(), true)
})
