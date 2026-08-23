import { create } from "zustand"

type InspectorTab = "evidence" | "activity" | "plan" | "context"
type DesktopUpdatePhase = "idle" | "downloading" | "ready" | "failed"

export interface DesktopUpdateState {
  phase: DesktopUpdatePhase
  stage?: "check" | "download"
  version?: string
  percent?: number
  transferred?: number
  total?: number
  bytesPerSecond?: number
}

interface UiState {
  currentProjectId: string
  mobileNavOpen: boolean
  inspectorOpen: boolean
  inspectorTab: InspectorTab
  desktopUpdate: DesktopUpdateState
  desktopVersion: string
  setMobileNavOpen: (open: boolean) => void
  setCurrentProjectId: (projectId: string) => void
  openInspector: (tab: InspectorTab) => void
  setInspectorOpen: (open: boolean) => void
  setDesktopUpdate: (update: DesktopUpdateState) => void
  setDesktopVersion: (version: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  currentProjectId: "",
  mobileNavOpen: false,
  inspectorOpen: false,
  inspectorTab: "evidence",
  desktopUpdate: { phase: "idle" },
  desktopVersion: "",
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
  setCurrentProjectId: (currentProjectId) => set({ currentProjectId }),
  openInspector: (inspectorTab) => set({ inspectorOpen: true, inspectorTab }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
  setDesktopUpdate: (desktopUpdate) => set({ desktopUpdate }),
  setDesktopVersion: (desktopVersion) => set({ desktopVersion }),
}))
