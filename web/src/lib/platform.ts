export interface DesktopWindowControls {
  minimize: () => Promise<void>
  toggleMaximize: () => Promise<boolean>
  close: () => Promise<void>
  checkForUpdates: () => Promise<{ supported: boolean; status: "unsupported" | "up-to-date" | "available" | "failed"; version?: string; reason?: "development" | "system-managed" | "unavailable" }>
  installUpdate: () => Promise<{ supported: boolean; status: "unsupported" | "not-ready" | "installing"; reason?: "development" | "system-managed" | "unavailable" }>
  appVersion: () => Promise<string>
  relaunchApp: () => Promise<void>
  openLogs: () => Promise<string>
  gpuPackStatus: () => Promise<DesktopGpuPackStatus>
  enableGpuPack: () => Promise<{ ok: boolean; phase: string }>
  disableGpuPack: () => Promise<{ ok: boolean }>
  onGpuPackStatus: (listener: (status: DesktopGpuPackStatus) => void) => () => void
  onUpdateStatus: (listener: (status: DesktopUpdateStatus) => void) => () => void
}

export interface DesktopGpuPackStatus {
  phase: "cpu-active" | "downloading" | "extracting" | "gpu-active" | "error"
  percent?: number
  received?: number
  total?: number
  error?: string
}

export interface DesktopUpdateStatus {
  status: "downloading" | "progress" | "ready" | "failed"
  stage?: "check" | "download"
  version?: string
  percent?: number
  transferred?: number
  total?: number
  bytesPerSecond?: number
}

declare global {
  interface Window {
    papersageDesktop?: DesktopWindowControls
  }
}

/**
 * The only renderer-side platform boundary. Web builds have no bridge and
 * therefore retain exactly the same pages and API behaviour as desktop builds.
 */
export function desktopWindowControls(): DesktopWindowControls | undefined {
  return typeof window === "undefined" ? undefined : window.papersageDesktop
}
