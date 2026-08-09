/**
 * @typedef {{ createFromPath: (path: string) => { isEmpty: () => boolean, setTemplateImage: (value: boolean) => void } }} NativeImage
 * @typedef {{ buildFromTemplate: (items: Array<{ label: string, click: () => void }>) => unknown }} ElectronMenu
 * @typedef {new (icon: unknown) => { setToolTip: (text: string) => void, setContextMenu: (menu: unknown) => void, on: (event: string, listener: () => void) => void }} ElectronTray
 */

/**
 * Owns the desktop tray lifecycle and explicit quit intent.
 * @param {{ Tray: ElectronTray, Menu: ElectronMenu, nativeImage: NativeImage, app: { quit: () => void }, iconPath: string, showWindow: () => void, platform?: NodeJS.Platform }} dependencies
 * @returns {{ beginQuit: () => void, isQuitting: () => boolean }}
 */
function createTrayService({ Tray, Menu, nativeImage, app, iconPath, showWindow, platform = process.platform }) {
  const icon = nativeImage.createFromPath(iconPath)
  if (platform === "darwin" && !icon.isEmpty()) icon.setTemplateImage(true)

  let quitting = false
  const beginQuit = () => { quitting = true }
  const quit = () => {
    beginQuit()
    app.quit()
  }
  const tray = new Tray(icon)
  tray.setToolTip("PaperSage")
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "显示 PaperSage", click: showWindow },
    { label: "退出 PaperSage", click: quit },
  ]))
  tray.on("click", showWindow)

  return { beginQuit, isQuitting: () => quitting }
}

module.exports = { createTrayService }
