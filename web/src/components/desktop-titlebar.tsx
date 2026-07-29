import type { CSSProperties } from "react"
import { Maximize2, Minimize2, X } from "lucide-react"

import { PaperSageBrand } from "@/components/papersage-logo"
import { Button } from "@/components/ui/button"
import { desktopWindowControls } from "@/lib/platform"

const dragRegion = { WebkitAppRegion: "drag" } as CSSProperties
const noDragRegion = { WebkitAppRegion: "no-drag" } as CSSProperties

export function DesktopTitlebar() {
  const controls = desktopWindowControls()
  if (!controls) return null
  const invoke = (action: () => Promise<unknown>): void => { void action() }
  return <div data-desktop-titlebar className="fixed inset-x-0 top-0 z-50 flex h-9 items-center border-b bg-background/90 pl-3 backdrop-blur" style={dragRegion}>
    <PaperSageBrand className="text-xs text-muted-foreground" />
    <div className="ml-auto flex h-full" style={noDragRegion}>
      <Button variant="ghost" size="icon" className="h-9 w-11 rounded-none" aria-label="最小化" onClick={() => invoke(controls.minimize)}><Minimize2 className="size-3.5" /></Button>
      <Button variant="ghost" size="icon" className="h-9 w-11 rounded-none" aria-label="最大化或还原" onClick={() => invoke(controls.toggleMaximize)}><Maximize2 className="size-3.5" /></Button>
      <Button variant="ghost" size="icon" className="h-9 w-11 rounded-none hover:bg-destructive hover:text-destructive-foreground" aria-label="关闭" onClick={() => invoke(controls.close)}><X className="size-4" /></Button>
    </div>
  </div>
}
