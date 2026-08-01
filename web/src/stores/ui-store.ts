import { create } from "zustand"

type InspectorTab = "evidence" | "activity" | "plan" | "context"

interface UiState {
  currentProjectId: string
  mobileNavOpen: boolean
  inspectorOpen: boolean
  inspectorTab: InspectorTab
  setMobileNavOpen: (open: boolean) => void
  setCurrentProjectId: (projectId: string) => void
  openInspector: (tab: InspectorTab) => void
  setInspectorOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>((set) => ({
  currentProjectId: "",
  mobileNavOpen: false,
  inspectorOpen: false,
  inspectorTab: "evidence",
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
  setCurrentProjectId: (currentProjectId) => set({ currentProjectId }),
  openInspector: (inspectorTab) => set({ inspectorOpen: true, inspectorTab }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
}))
