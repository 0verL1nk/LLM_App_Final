import { useEffect } from "react"
import { toast } from "sonner"

import { desktopWindowControls } from "@/lib/platform"
import { useUiStore } from "@/stores/ui-store"

function formatBytes(value?: number): string {
  if (!value) return ""
  const units = ["B", "KB", "MB", "GB"]
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  return `${(value / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function DesktopUpdateStatusListener(): null {
  const desktop = desktopWindowControls()
  const setDesktopUpdate = useUiStore((state) => state.setDesktopUpdate)
  const setDesktopVersion = useUiStore((state) => state.setDesktopVersion)

  useEffect(() => {
    if (!desktop) return
    desktop.appVersion().then((value) => setDesktopVersion(value)).catch(() => undefined)
    return desktop.onUpdateStatus((status) => {
      if (status.status === "downloading") {
        setDesktopUpdate({ phase: "downloading", version: status.version, percent: 0 })
        toast.loading("正在下载更新", { id: "desktop-update", description: "下载期间可以继续使用 PaperSage。" })
        return
      }
      if (status.status === "progress") {
        const percent = Math.round(status.percent ?? 0)
        const detail = status.total
          ? `已完成 ${percent}% · ${formatBytes(status.transferred)} / ${formatBytes(status.total)}`
          : `已完成 ${percent}%`
        setDesktopUpdate({ phase: "downloading", ...status, percent })
        toast.loading("正在下载更新", { id: "desktop-update", description: detail })
        return
      }
      if (status.status === "ready") {
        setDesktopUpdate({ phase: "ready" })
        toast.success("更新已下载完成", {
          id: "desktop-update",
          description: "重启 PaperSage 即可完成安装，也可以下次退出时自动安装。",
          action: { label: "重启并更新", onClick: () => void desktop.installUpdate() },
        })
        return
      }
      setDesktopUpdate({ phase: "failed", stage: status.stage })
      if (status.stage === "check") {
        toast.error("检查更新失败", {
          id: "desktop-update",
          description: "无法连接更新源，稍后会自动重试。受限网络可设置 PAPERSAGE_UPDATE_FEED 镜像源。",
        })
        return
      }
      toast.error("下载未完成", { id: "desktop-update", description: "请检查网络后再试一次。" })
    })
  }, [desktop, setDesktopUpdate, setDesktopVersion])

  return null
}
