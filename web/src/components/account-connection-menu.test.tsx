// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AccountConnectionMenu } from "@/components/account-connection-menu"

describe("AccountConnectionMenu", () => {
  it("offers exactly one settings entry that opens the settings page", () => {
    const onOpenSettings = vi.fn()
    render(<AccountConnectionMenu onOpenSettings={onOpenSettings} />)

    const trigger = screen.getByRole("button", { name: "打开账户与连接设置" })
    fireEvent.pointerDown(trigger, { button: 0 })
    fireEvent.click(trigger)

    expect(screen.getAllByText("设置")).toHaveLength(1)
    fireEvent.click(screen.getByText("设置"))
    expect(onOpenSettings).toHaveBeenCalledOnce()
  })
})
