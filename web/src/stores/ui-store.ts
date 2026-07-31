import { create } from "zustand"

type InspectorTab = "evidence" | "activity" | "plan" | "context"

interface UiState {
  mobileNavOpen: boolean
  inspectorOpen: boolean
  inspectorTab: InspectorTab
  setMobileNavOpen: (open: boolean) => void
  openInspector: (tab: InspectorTab) => void
  setInspectorOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>((set) => ({
  mobileNavOpen: false,
  inspectorOpen: false,
  inspectorTab: "evidence",
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
  openInspector: (inspectorTab) => set({ inspectorOpen: true, inspectorTab }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
}))
