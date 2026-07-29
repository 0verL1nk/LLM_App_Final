// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ResearchSessionList } from "@/components/research-session-list"

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, onClick, ...props }: React.ComponentProps<"a">) => <a {...props} onClick={onClick}>{children}</a>,
}))

describe("ResearchSessionList", () => {
  it("marks the current session and closes its mobile sheet after a selection", () => {
    const onSelect = vi.fn()
    render(<ResearchSessionList projectId="project-1" selectedSessionId="session-2" onSelect={onSelect} sessions={[
      { session_uid: "session-1", session_name: "文献梳理", message_count: 3, is_pinned: 0, is_main: true, parent_session_uid: "" },
      { session_uid: "session-2", session_name: "方法比较", message_count: 8, is_pinned: 0, is_main: false, parent_session_uid: "session-1" },
    ]} />)

    const active = screen.getByText("方法比较").closest("a")
    expect(active?.getAttribute("aria-current")).toBe("page")
    fireEvent.click(screen.getByText("文献梳理"))
    expect(onSelect).toHaveBeenCalledOnce()
  })
})
