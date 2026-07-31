const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("papersageDesktop", {
  minimize: () => ipcRenderer.invoke("window:minimize"),
  toggleMaximize: () => ipcRenderer.invoke("window:toggle-maximize"),
  close: () => ipcRenderer.invoke("window:close"),
})
