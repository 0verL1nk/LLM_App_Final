import { z } from "zod"

const API_ROOT = "/api/v1"

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json")
  headers.set("X-User-Id", "local-user")
  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  const envelope = await response.json()
  return schema.parse(envelope.data)
}

export async function upload<T>(path: string, file: File, schema: z.ZodType<T>): Promise<T> {
  const body = new FormData()
  body.set("file", file)
  return api(path, schema, { method: "POST", body })
}

export async function consumeEventStream(
  path: string,
  onEvent: (payload: unknown) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(path.startsWith("/api/") ? path : `${API_ROOT}${path}`, {
    headers: { Accept: "text/event-stream", "X-User-Id": "local-user" }, signal,
  })
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(response.status, body?.detail ?? `Event stream failed (${response.status})`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n")
    const frames = buffer.split("\n\n")
    buffer = frames.pop() ?? ""
    for (const frame of frames) {
      const data = frame.split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n")
      if (data) onEvent(JSON.parse(data))
    }
    if (done) break
  }
}
