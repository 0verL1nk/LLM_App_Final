import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { z } from "zod"

import { api, consumeEventStream, upload } from "@/lib/api"
import {
  agentEventSchema,
  documentSchema,
  documentConversionSchema,
  messageSchema,
  projectSchema,
  runCreatedSchema,
  runSchema,
  researchArtifactSchema,
  steeringInputSchema,
  sessionSchema,
  settingsSchema,
  turnResultSchema,
} from "@/lib/schemas"
import type { AgentEvent, Document, Message } from "@/lib/schemas"

export const keys = {
  projects: ["projects"] as const,
  project: (id: string) => ["projects", id] as const,
  documents: (id: string) => ["projects", id, "documents"] as const,
  sessions: (id: string) => ["projects", id, "sessions"] as const,
  messages: (projectId: string, sessionId: string) => ["messages", projectId, sessionId] as const,
  resumableRuns: (projectId: string, sessionId: string) => ["runs", projectId, sessionId, "resumable"] as const,
  researchArtifacts: (projectId: string, sessionId: string) => ["research-artifacts", projectId, sessionId] as const,
  settings: ["settings"] as const,
}

export function useProjects() {
  return useQuery({ queryKey: keys.projects, queryFn: () => api("/projects", z.array(projectSchema)) })
}

export function useProject(projectId: string) {
  return useQuery({ queryKey: keys.project(projectId), queryFn: () => api(`/projects/${projectId}`, projectSchema) })
}

export function useDocuments(projectId: string) {
  return useQuery({
    queryKey: keys.documents(projectId),
    queryFn: () => api(`/projects/${projectId}/documents`, z.array(documentSchema)),
    refetchInterval: (query) => query.state.data?.some((item) => ["queued", "running"].includes(item.ingestion?.status ?? "")) ? 1500 : false,
  })
}

export function useSessions(projectId: string, enabled = true) {
  return useQuery({
    queryKey: keys.sessions(projectId),
    queryFn: () => api(`/projects/${projectId}/sessions`, z.array(sessionSchema)),
    enabled,
  })
}

export function useMessages(projectId: string, sessionId: string) {
  return useQuery({
    queryKey: keys.messages(projectId, sessionId),
    queryFn: () => api(`/projects/${projectId}/sessions/${sessionId}/messages?limit=200`, z.array(messageSchema)),
  })
}

export function useResumableRuns(projectId: string, sessionId: string) {
  return useQuery({
    queryKey: keys.resumableRuns(projectId, sessionId),
    queryFn: () => api(`/projects/${projectId}/sessions/${sessionId}/runs`, z.array(runSchema)),
    refetchInterval: (query) => query.state.data?.length ? 1500 : false,
  })
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api("/settings", settingsSchema) })
}

export function useResearchArtifacts(projectId: string, sessionId: string) {
  return useQuery({
    queryKey: keys.researchArtifacts(projectId, sessionId),
    queryFn: () => api(`/projects/${projectId}/sessions/${sessionId}/research-artifacts`, z.object({ data: z.array(researchArtifactSchema) })).then((result) => result.data),
  })
}

export function useDocumentConversion() {
  return useQuery({ queryKey: ["document-conversion"], queryFn: () => api("/document-conversion", documentConversionSchema) })
}

export function useCreateProject() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { project_name: string; description: string }) => api("/projects", projectSchema, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects }),
  })
}

export function useCreateSession(projectId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (session_name: string) => api(`/projects/${projectId}/sessions`, sessionSchema, { method: "POST", body: JSON.stringify({ session_name }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.sessions(projectId) }),
  })
}

export interface UploadBatchResult {
  uploaded: string[]
  documents: Document[]
  failed: Array<{ fileName: string; message: string }>
}

export function useUploadDocuments(projectId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (files: File[]): Promise<UploadBatchResult> => {
      const results = await Promise.allSettled(
        files.map((file) => upload(`/projects/${projectId}/documents`, file, documentSchema)),
      )
      return results.reduce<UploadBatchResult>((summary, result, index) => {
        const fileName = files[index]?.name ?? "未知文件"
        if (result.status === "fulfilled") {
          summary.uploaded.push(fileName)
          summary.documents.push(result.value)
        } else {
          summary.failed.push({
            fileName,
            message: result.reason instanceof Error ? result.reason.message : "上传失败",
          })
        }
        return summary
      }, { uploaded: [], documents: [], failed: [] })
    },
    onSuccess: (result) => {
      client.setQueryData<Document[]>(keys.documents(projectId), (current = []) => {
        const received = new Map(result.documents.map((document) => [document.uid, document]))
        return [...result.documents, ...current.filter((document) => !received.has(document.uid))]
      })
    },
    onSettled: () => client.invalidateQueries({ queryKey: keys.documents(projectId) }),
  })
}

export function useRetryDocument(projectId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (docId: string) => api(`/projects/${projectId}/documents/${docId}/retry`, z.unknown(), { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.documents(projectId) }),
  })
}

export function useTurn(projectId: string, sessionId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ prompt, executionMode = "auto", onEvent, onRunCreated }: { prompt: string; executionMode?: "auto" | "react" | "plan_execute" | "agent_teams"; onEvent: (event: AgentEvent) => void; onRunCreated?: (runId: string) => void }) => {
      const run = await api(
        `/projects/${projectId}/sessions/${sessionId}/runs`,
        runCreatedSchema,
        {
          method: "POST",
          body: JSON.stringify({ prompt, execution_mode: executionMode, client_request_id: crypto.randomUUID() }),
        },
      )
      onRunCreated?.(run.run_id)
      void client.invalidateQueries({ queryKey: keys.resumableRuns(projectId, sessionId) })
      let result: z.infer<typeof turnResultSchema> | undefined
      let failure: string | undefined
      const handleEvent = (rawEvent: unknown) => {
        const event = agentEventSchema.parse(rawEvent)
        onEvent(event)
        if (event.eventType === "run.completed") {
          // Some terminal paths emit a null result; surface it through the
          // "no final answer" branch instead of a raw ZodError message.
          const raw = event.payload.result
          result = raw == null ? undefined : turnResultSchema.parse(raw)
        } else if (event.eventType === "run.failed") {
          failure = String(event.payload.message ?? "Agent 运行失败")
        }
      }
      await consumeEventStream(run.stream_url, handleEvent)
      if (!result && !failure) {
        // A transient stream drop (e.g., localhost fetch failure while the
        // machine is fully loaded) ends the stream without a terminal event.
        // Reconnect once: the endpoint replays the persisted event log and
        // closes it after the terminal event.
        await consumeEventStream(run.stream_url, handleEvent)
      }
      if (failure) throw new Error(failure)
      if (!result) throw new Error("Run 已结束，但没有返回最终结果")
      return result
    },
    onMutate: async ({ prompt }) => {
      await client.cancelQueries({ queryKey: keys.messages(projectId, sessionId) })
      client.setQueryData<Message[]>(keys.messages(projectId, sessionId), (current = []) => [
        ...current,
        { role: "user", content: prompt },
      ])
    },
    onSuccess: (result) => {
      client.setQueryData<Message[]>(keys.messages(projectId, sessionId), (current = []) => [
        ...current,
        {
          role: "assistant",
          content: result.answer,
          trace: result.trace_payload,
          evidence: result.evidence_items,
          retrieved_evidence: result.retrieved_evidence_items,
          plan: result.agent_plan ?? result.plan,
          todos: result.todos,
          a2ui: result.a2ui_surface,
        },
      ])
      void client.invalidateQueries({ queryKey: keys.messages(projectId, sessionId) })
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: keys.messages(projectId, sessionId) })
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.sessions(projectId) })
      void client.invalidateQueries({ queryKey: keys.researchArtifacts(projectId, sessionId) })
    },
  })
}

export function useSteeringInput(projectId: string, sessionId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (prompt: string) => api(
      `/projects/${projectId}/sessions/${sessionId}/steering-inputs`,
      steeringInputSchema,
      { method: "POST", body: JSON.stringify({ prompt, client_request_id: crypto.randomUUID() }) },
    ),
    onSuccess: (_input, prompt) => {
      client.setQueryData<Message[]>(keys.messages(projectId, sessionId), (current = []) => [
        ...current,
        { role: "user", content: prompt },
      ])
      void client.invalidateQueries({ queryKey: keys.resumableRuns(projectId, sessionId) })
    },
  })
}
