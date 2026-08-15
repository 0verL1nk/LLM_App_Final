import { z } from "zod"

export const projectSchema = z.object({
  project_uid: z.string(),
  project_name: z.string(),
  description: z.string().default(""),
  created_at: z.string().nullish(),
  updated_at: z.string().nullish(),
  archived: z.coerce.number().default(0),
})

export const ingestionSchema = z.object({
  status: z.string(),
  stage: z.string(),
  current_items: z.number().nullable(),
  total_items: z.number().nullable(),
  error_message: z.string().nullable(),
  index_version: z.string().nullable(),
}).nullable().optional()

export const documentSchema = z.object({
  uid: z.string(),
  file_name: z.string(),
  file_path: z.string(),
  created_at: z.string().nullish(),
  is_active: z.coerce.number().default(1),
  ingestion: ingestionSchema,
})

export const sessionSchema = z.object({
  session_uid: z.string(),
  session_name: z.string(),
  updated_at: z.string().nullish(),
  created_at: z.string().nullish(),
  is_pinned: z.coerce.number().default(0),
  is_main: z.boolean().default(false),
  parent_session_uid: z.string().default(""),
  message_count: z.coerce.number().default(0),
  last_message: z.string().nullish(),
})

export const messageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]).catch("assistant"),
  content: z.string(),
  trace: z.array(z.record(z.string(), z.unknown())).optional(),
  evidence: z.array(z.record(z.string(), z.unknown())).optional(),
  retrieved_evidence: z.array(z.record(z.string(), z.unknown())).optional(),
  plan: z.record(z.string(), z.unknown()).nullable().optional(),
  todos: z.array(z.record(z.string(), z.unknown())).optional(),
  a2ui: z.union([z.record(z.string(), z.unknown()), z.array(z.record(z.string(), z.unknown()))]).nullable().optional(),
  parts: z.array(z.record(z.string(), z.unknown())).optional(),
  context_snapshot: z.record(z.string(), z.unknown()).optional(),
})

export const settingsSchema = z.object({
  api_key_configured: z.boolean(),
  api_key_hint: z.string(),
  model_name: z.string(),
  base_url: z.string(),
  rag_index_batch_size: z.number().nullable().optional(),
  local_rag_project_max_chars: z.number().nullable().optional(),
  local_rag_project_max_chunks: z.number().nullable().optional(),
})

export const ocrRuntimeSchema = z.object({
  profile: z.string(),
  device: z.string(),
  gpu_enabled: z.boolean(),
  driver_available: z.boolean().nullish(),
})

export const documentConversionSchema = z.object({
  microsoft_office: z.boolean(),
  libreoffice: z.boolean(),
  office_preview_ready: z.boolean(),
  ocr: ocrRuntimeSchema.nullish(),
})

export const turnResultSchema = z.object({
  answer: z.string(),
  trace_payload: z.array(z.record(z.string(), z.unknown())).default([]),
  evidence_items: z.array(z.record(z.string(), z.unknown())).default([]),
  retrieved_evidence_items: z.array(z.record(z.string(), z.unknown())).default([]),
  plan: z.record(z.string(), z.unknown()).nullable().optional(),
  agent_plan: z.record(z.string(), z.unknown()).nullable().optional(),
  todos: z.array(z.record(z.string(), z.unknown())).default([]),
  run_latency_ms: z.number().default(0),
  phase_path: z.string().default(""),
  used_document_rag: z.boolean().default(false),
  a2ui_surface: z.record(z.string(), z.unknown()).nullable().optional(),
  context_snapshot: z.record(z.string(), z.unknown()).optional(),
})

export const runCreatedSchema = z.object({
  run_id: z.string(),
  status: z.string(),
  stream_url: z.string(),
  requested_mode: z.enum(["auto", "react", "plan_execute", "agent_teams"]),
  resolved_mode: z.enum(["react", "plan_execute", "agent_teams"]),
  route_reason: z.string(),
})

export const runSchema = z.object({
  run_uid: z.string(),
  project_uid: z.string(),
  session_uid: z.string(),
  status: z.string(),
  prompt: z.string(),
  created_at: z.string().nullish(),
  updated_at: z.string().nullish(),
})

export const agentEventSchema = z.object({
  version: z.union([z.literal(1), z.literal(2)]),
  eventId: z.string(),
  eventType: z.string(),
  sequence: z.number().int().positive(),
  timestamp: z.string(),
  threadId: z.string(),
  runId: z.string(),
  traceId: z.string(),
  payload: z.record(z.string(), z.unknown()).default({}),
  item: z.object({
    id: z.string(),
    type: z.string(),
    status: z.string(),
    taskId: z.string().nullable().optional(),
    payload: z.record(z.string(), z.unknown()).default({}),
  }).optional(),
})

export const steeringInputSchema = z.object({
  input_id: z.string(),
  run_id: z.string(),
  status: z.string(),
})

const bboxSchema = z.tuple([z.number(), z.number(), z.number(), z.number()])

export const evidenceReferenceSchema = z.object({
  chunk_id: z.string().min(1),
  doc_uid: z.string().min(1),
  page_no: z.number().int().nullish(),
  offset_start: z.number().int().nullish(),
  offset_end: z.number().int().nullish(),
  bbox: bboxSchema.nullish(),
  source_url: z.string().default(""),
})

export const claimTypeSchema = z.enum(["paper_fact", "hypothesis", "cross_paper_synthesis"])

export const atomicClaimSchema = z.object({
  statement: z.string().min(1),
  evidence_refs: z.array(z.string()).default([]),
  claim_type: claimTypeSchema.default("paper_fact"),
  limitation: z.string().default(""),
})

const packetLimitationSchema = z.object({
  kind: z.string().default("general"),
  statement: z.string().min(1),
  evidence_refs: z.array(z.string()).default([]),
})

const openQuestionSchema = z.object({
  question: z.string().min(1),
  suggested_action: z.string().default(""),
  evidence_refs: z.array(z.string()).default([]),
})

export const evidencePacketSchema = z.object({
  research_question: z.string().default(""),
  summary: z.string().min(1),
  evidence_refs: z.array(z.string()).default([]),
  claims: z.array(atomicClaimSchema).default([]),
  evidence: z.array(evidenceReferenceSchema).default([]),
  limitations: z.array(z.union([z.string(), packetLimitationSchema])).default([]),
  open_questions: z.array(z.union([z.string(), openQuestionSchema])).default([]),
  confidence: z.number().min(0).max(1).default(0.5),
  metrics: z.record(z.string(), z.number()).default({}),
})

export const reviewFindingKindSchema = z.enum([
  "over_claim",
  "insufficient_evidence",
  "method_result_confusion",
  "missed_counterexample",
  "terminology_inconsistency",
  "citation_gap",
])

export const writingBriefSchema = z.object({
  audience: z.string().min(1),
  purpose: z.string().min(1),
  target_section: z.string().default(""),
  claim_budget: z.number().int().min(0).default(0),
  style_constraints: z.array(z.string()).default([]),
})

export const draftRevisionSchema = z.object({
  section: z.string().default(""),
  text: z.string().default(""),
  claim_ids: z.array(z.string()).default([]),
  evidence_refs: z.array(z.string()).default([]),
  claim_spans: z
    .array(
      z.object({
        claim_id: z.string(),
        start: z.number().int().min(0),
        end: z.number().int().min(1),
        evidence_refs: z.array(z.string()).default([]),
        note: z.string().default(""),
      }),
    )
    .default([]),
  rationale: z.string().default(""),
  unsupported_claims: z.array(z.string()).default([]),
  citation_gaps: z.array(z.string()).default([]),
  review_findings: z
    .array(
      z.object({
        kind: reviewFindingKindSchema,
        location: z.string().default(""),
        note: z.string().default(""),
      }),
    )
    .default([]),
  based_on_revision: z.string().default(""),
})

export const researchArtifactRevisionSchema = z.object({
  revision_uid: z.string(),
  artifact_uid: z.string(),
  revision: z.number().int().min(1),
  status: z.enum(["proposed", "accepted", "rejected", "superseded"]),
  content: z.record(z.string(), z.unknown()).default({}),
  evidence_refs: z.array(z.string()).default([]),
  source_run_uid: z.string().default(""),
  source_task_uid: z.string().default(""),
  based_on_revision_uid: z.string().default(""),
  decision_note: z.string().default(""),
  decided_at: z.string().default(""),
  created_at: z.string().nullish(),
})

export const researchArtifactSchema = z.object({
  artifact_uid: z.string(),
  uuid: z.string().default(""),
  run_uid: z.string().nullish().transform((value) => value ?? ""),
  task_uid: z.string().nullish().transform((value) => value ?? ""),
  artifact_type: z.string(),
  content: z.record(z.string(), z.unknown()).default({}),
  evidence_refs: z.array(z.string()).default([]),
  created_at: z.string().nullish(),
})

export type Project = z.infer<typeof projectSchema>
export type Document = z.infer<typeof documentSchema>
export type Session = z.infer<typeof sessionSchema>
export type Message = z.infer<typeof messageSchema>
export type Settings = z.infer<typeof settingsSchema>
export type TurnResult = z.infer<typeof turnResultSchema>
export type AgentEvent = z.infer<typeof agentEventSchema>
export type Run = z.infer<typeof runSchema>
export type SteeringInput = z.infer<typeof steeringInputSchema>
export type ResearchArtifact = z.infer<typeof researchArtifactSchema>
