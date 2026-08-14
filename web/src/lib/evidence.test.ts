import { describe, expect, it } from "vitest"

import { formatEvidenceCitations } from "@/lib/evidence"

describe("formatEvidenceCitations", () => {
  it("replaces a raw evidence protocol tag with a numbered citation", () => {
    const rendered = formatEvidenceCitations(
      "结论成立<evidence>chunk-1|p1|o10-20</evidence>。",
      [{ chunk_id: "chunk-1", text: "source" }],
    )

    expect(rendered).not.toContain("<evidence>")
    expect(rendered).toContain("[1](#evidence-chunk-1%7Cp1%7Co10-20")
  })

  it("hides the protocol syntax even when evidence details are unavailable", () => {
    const rendered = formatEvidenceCitations("内容<evidence>missing|p2|o1-3</evidence>")

    expect(rendered).toContain("[引用]")
    expect(rendered).not.toContain("<evidence>")
  })
})
