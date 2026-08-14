/**
 * @typedef {{ createFromPath: (path: string) => { isEmpty: () => boolean, setTemplateImage: (value: boolean) => void } }} NativeImage
 * @typedef {{ buildFromTemplate: (items: Array<{ label: string, click: () => void }>) => unknown }} ElectronMenu
 * @typedef {new (icon: unknown) => { setToolTip: (text: string) => void, setContextMenu: (menu: unknown) => void, on: (event: string, listener: () => void) => void }} ElectronTray
 */

/**
 * Owns the desktop tray lifecycle and explicit quit intent.
 * @param {{ Tray: ElectronTray, Menu: ElectronMenu, nativeImage: NativeImage, app: { quit: () => void }, iconPath: string, showWindow: () => void, platform?: NodeJS.Platform, reportError?: (message: string) => void }} dependencies
 * @returns {{ beginQuit: () => void, isQuitting: () => boolean }}
 */
function createTrayService({ Tray, Menu, nativeImage, app, iconPath, showWindow, platform = process.platform, reportError }) {
  const icon = nativeImage.createFromPath(iconPath)
  // nativeImage only decodes PNG/JPEG; anything else (e.g. SVG) loads as an
  // empty image and the tray silently goes invisible. Surface that loudly.
  if (icon.isEmpty()) reportError?.(`托盘图标加载失败（解码为空图像，nativeImage 仅支持 PNG/JPEG）：${iconPath}`)

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
