export interface DesktopWindowControls {
  minimize: () => Promise<void>
  toggleMaximize: () => Promise<boolean>
  close: () => Promise<void>
  checkForUpdates: () => Promise<{ supported: boolean; status: "unsupported" | "up-to-date" | "available" | "failed"; version?: string }>
  onUpdateStatus: (listener: (status: DesktopUpdateStatus) => void) => () => void
}

export interface DesktopUpdateStatus {
  status: "downloading" | "progress" | "ready" | "failed"
  version?: string
  percent?: number
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
