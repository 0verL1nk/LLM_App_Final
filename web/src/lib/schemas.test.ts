import { describe, expect, it } from "vitest"

import { documentSchema, turnResultSchema } from "@/lib/schemas"

describe("API schemas", () => {
  it("normalizes document ingestion state", () => {
    const document = documentSchema.parse({
      uid: "d1",
      file_name: "paper.pdf",
      file_path: "/paper.pdf",
      ingestion: {
        status: "running",
        stage: "embedding",
        current_items: 4,
        total_items: 10,
        error_message: null,
        index_version: null,
      },
    })
    expect(document.ingestion?.stage).toBe("embedding")
  })

  it("requires a final answer in turn payloads", () => {
    expect(() => turnResultSchema.parse({ trace_payload: [] })).toThrow()
  })
})
