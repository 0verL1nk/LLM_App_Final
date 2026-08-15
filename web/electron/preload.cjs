const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("papersageDesktop", {
  minimize: () => ipcRenderer.invoke("window:minimize"),
  toggleMaximize: () => ipcRenderer.invoke("window:toggle-maximize"),
  close: () => ipcRenderer.invoke("window:close"),
  checkForUpdates: () => ipcRenderer.invoke("updates:check"),
  installUpdate: () => ipcRenderer.invoke("updates:install"),
  appVersion: () => ipcRenderer.invoke("app:version"),
  relaunchApp: () => ipcRenderer.invoke("app:relaunch"),
  openLogs: () => ipcRenderer.invoke("logs:open"),
  gpuPackStatus: () => ipcRenderer.invoke("gpu-pack:status"),
  enableGpuPack: () => ipcRenderer.invoke("gpu-pack:enable"),
  disableGpuPack: () => ipcRenderer.invoke("gpu-pack:disable"),
  onGpuPackStatus: (listener) => {
    const handler = (_event, status) => listener(status)
    ipcRenderer.on("gpu-pack:status", handler)
    return () => ipcRenderer.removeListener("gpu-pack:status", handler)
  },
  onUpdateStatus: (listener) => {
    const handler = (_event, status) => listener(status)
    ipcRenderer.on("updates:status", handler)
    return () => ipcRenderer.removeListener("updates:status", handler)
  },
})
