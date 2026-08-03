const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("papersageDesktop", {
  minimize: () => ipcRenderer.invoke("window:minimize"),
  toggleMaximize: () => ipcRenderer.invoke("window:toggle-maximize"),
  close: () => ipcRenderer.invoke("window:close"),
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  onUpdateStatus: (listener) => {
    const handler = (_event, status) => listener(status)
    ipcRenderer.on("updates:status", handler)
    return () => ipcRenderer.removeListener("updates:status", handler)
  },
})
