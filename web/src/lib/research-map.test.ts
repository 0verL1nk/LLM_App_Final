// @vitest-environment jsdom
import { describe, expect, it } from "vitest"

import { parseResearchMap } from "@/lib/research-map"

describe("parseResearchMap", () => {
  it("parses a complete map with nested nodes and citations", () => {
    const parsed = parseResearchMap(
      '<map title="论文结构"><node label="方法"><node label="训练目标" /><evidence ref="chunk-1" /><node label="网络架构"><evidence ref="chunk-2" /></node></node></map>',
    )
    expect(parsed?.title).toBe("论文结构")
    expect(parsed?.root.label).toBe("方法")
    expect(parsed?.root.citationIds).toEqual(["chunk-1"])
    expect(parsed?.root.children.map((child) => child.label)).toEqual(["训练目标", "网络架构"])
    expect(parsed?.root.children[1]?.citationIds).toEqual(["chunk-2"])
  })

  it("truncates over-limit children and labels instead of dropping the map", () => {
    const children = Array.from({ length: 20 }, (_, index) => `<node label="分支${index}" />`).join("")
    const longLabel = "超长".repeat(100)
    const parsed = parseResearchMap(`<map title="极限"><node label="${longLabel}">${children}</node></map>`)
    expect(parsed?.root.children).toHaveLength(12)
    expect(parsed?.root.label.length).toBe(120)
  })

  it("returns null for unrecognizable structures", () => {
    expect(parseResearchMap("")).toBeNull()
    expect(parseResearchMap("<div>不是导图</div>")).toBeNull()
    expect(parseResearchMap('<map title="缺节点"></map>')).toBeNull()
    expect(parseResearchMap('<map><node label="缺标题" /></map>')).toBeNull()
  })
})
