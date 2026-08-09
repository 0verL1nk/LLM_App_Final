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
  delegation: z.record(z.string(), z.unknown()).optional(),
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

export const documentConversionSchema = z.object({
  microsoft_office: z.boolean(),
  libreoffice: z.boolean(),
  office_preview_ready: z.boolean(),
})

export const turnResultSchema = z.object({
  answer: z.string(),
  trace_payload: z.array(z.record(z.string(), z.unknown())).default([]),
  evidence_items: z.array(z.record(z.string(), z.unknown())).default([]),
  retrieved_evidence_items: z.array(z.record(z.string(), z.unknown())).default([]),
  delegation_execution: z.record(z.string(), z.unknown()).default({}),
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
  version: z.literal(1),
  eventId: z.string(),
  eventType: z.string(),
  sequence: z.number().int().positive(),
  timestamp: z.string(),
  threadId: z.string(),
  runId: z.string(),
  traceId: z.string(),
  payload: z.record(z.string(), z.unknown()),
})

export type Project = z.infer<typeof projectSchema>
export type Document = z.infer<typeof documentSchema>
export type Session = z.infer<typeof sessionSchema>
export type Message = z.infer<typeof messageSchema>
export type Settings = z.infer<typeof settingsSchema>
export type TurnResult = z.infer<typeof turnResultSchema>
export type AgentEvent = z.infer<typeof agentEventSchema>
export type Run = z.infer<typeof runSchema>
