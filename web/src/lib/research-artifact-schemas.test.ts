import { describe, expect, it } from "vitest"

import {
  atomicClaimSchema,
  draftRevisionSchema,
  evidencePacketSchema,
  evidenceReferenceSchema,
  researchArtifactRevisionSchema,
  researchArtifactSchema,
  writingBriefSchema,
} from "@/lib/schemas"

const pydanticPacket = {
  research_question: "该方法是否有效？",
  summary: "两个数据集上错误率下降。",
  evidence_refs: ["chunk-a"],
  claims: [
    {
      statement: "错误率下降。",
      evidence_refs: ["chunk-a"],
      claim_type: "paper_fact",
      limitation: "",
    },
    {
      statement: "可能泛化。",
      evidence_refs: [],
      claim_type: "hypothesis",
      limitation: "",
    },
  ],
  evidence: [
    {
      chunk_id: "chunk-a",
      doc_uid: "doc-a",
      page_no: 3,
      offset_start: null,
      offset_end: null,
      bbox: [0.1, 0.2, 0.5, 0.8],
      source_url: "",
    },
  ],
  limitations: ["样本量小", { kind: "conflict", statement: "与另一篇相反", evidence_refs: ["chunk-a"] }],
  open_questions: ["能否泛化？", { question: "图 3 可靠吗？", suggested_action: "read_figure", evidence_refs: [] }],
  confidence: 0.6,
  metrics: { run_latency_ms: 12.5 },
}

describe("evidence packet zod contracts mirror the pydantic wire shape", () => {
  it("parses a serialized EvidencePacket with defaults applied", () => {
    const packet = evidencePacketSchema.parse(pydanticPacket)

    expect(packet.claims[0].claim_type).toBe("paper_fact")
    expect(packet.claims[1].claim_type).toBe("hypothesis")
    expect(packet.evidence[0].bbox).toEqual([0.1, 0.2, 0.5, 0.8])
    expect(packet.limitations[1]).toEqual({ kind: "conflict", statement: "与另一篇相反", evidence_refs: ["chunk-a"] })
    expect(packet.open_questions[1]).toEqual({ question: "图 3 可靠吗？", suggested_action: "read_figure", evidence_refs: [] })
    expect(packet.confidence).toBe(0.6)
  })

  it("rejects unknown claim types and out-of-range confidence", () => {
    expect(() => atomicClaimSchema.parse({ statement: "s", evidence_refs: [], claim_type: "guess" })).toThrow()
    expect(() => evidencePacketSchema.parse({ ...pydanticPacket, confidence: 1.5 })).toThrow()
  })

  it("requires coordinates to carry a chunk identity", () => {
    expect(() => evidenceReferenceSchema.parse({ chunk_id: "", doc_uid: "doc-a" })).toThrow()
  })
})

describe("writing contracts", () => {
  it("parses a draft revision with claim spans and review findings", () => {
    const revision = draftRevisionSchema.parse({
      section: "结果",
      text: "该方法降低了错误率。",
      claim_ids: ["claim-1"],
      evidence_refs: ["chunk-a"],
      claim_spans: [{ claim_id: "claim-1", start: 0, end: 6, evidence_refs: ["chunk-a"], note: "" }],
      rationale: "初稿",
      unsupported_claims: [],
      citation_gaps: [],
      review_findings: [{ kind: "over_claim", location: "第 2 句", note: "超出范围" }],
      based_on_revision: "",
    })

    expect(revision.claim_spans[0].end).toBe(6)
    expect(revision.review_findings[0].kind).toBe("over_claim")
    expect(writingBriefSchema.parse({ audience: "研究生", purpose: "解释" }).claim_budget).toBe(0)
  })
})

describe("artifact schemas tolerate run-less writing artifacts", () => {
  it("parses artifacts and revisions without a durable run or task", () => {
    const artifact = researchArtifactSchema.parse({
      artifact_uid: "artifact-1",
      run_uid: null,
      task_uid: null,
      artifact_type: "writing_draft",
      content: {},
      evidence_refs: ["chunk-a"],
      created_at: null,
    })
    expect(artifact.uuid).toBe("")

    const revision = researchArtifactRevisionSchema.parse({
      revision_uid: "revision-1",
      artifact_uid: "artifact-1",
      revision: 2,
      status: "superseded",
      content: {},
      evidence_refs: [],
      source_run_uid: "run-1",
      source_task_uid: "",
      based_on_revision_uid: "",
      decision_note: "已采用新版本",
      decided_at: "2026-08-15T00:00:00",
      created_at: null,
    })
    expect(revision.status).toBe("superseded")
  })
})
