# PaperSage Web Application

## Product model

The new interface is project-first rather than page-first. A project owns its
documents, sessions, retrieval scope, memories, and Agent activity. Uploading and
indexing never blocks conversation creation; ready documents appear in subsequent
turns automatically.

## Information architecture

- `/projects`: searchable project portfolio with create, rename, archive, and status.
- `/projects/$projectId`: project overview and recent research activity.
- `/projects/$projectId/research/$sessionId`: primary research workspace. Sessions
  are a compact rail, conversation is the main canvas, and evidence/activity opens
  in an inspector rather than navigating away.
- `/projects/$projectId/library`: document upload, project binding, ingestion progress,
  retry, and retrieval readiness.
- `/settings`: model provider and indexing controls with explicit validation.

Desktop uses a persistent application rail and contextual inspector. Mobile uses
Radix sheets: the research workspace exposes both session switching and new-session
creation without requiring the desktop-only session rail. Context tabs scroll rather
than clip on narrow screens, and the composer respects mobile safe-area insets.
Empty, loading, error, and destructive states are first-class UI.

## Frontend boundaries

- Vite + React + TypeScript is the independent client in `web/`.
- TanStack Router owns navigable state; no selected project/session is hidden in a
  component singleton.
- TanStack Query owns remote data, cache invalidation, polling, and mutations.
- Zustand owns UI-only state such as theme, mobile navigation, and inspector tabs.
- React Hook Form + Zod owns form state and client validation. API responses are
  validated with Zod at the boundary.
- shadcn/ui source components use Radix primitives, Tailwind tokens, Lucide icons,
  and a restrained editorial workspace theme.

## API boundary

FastAPI exposes `/api/v1` as a thin transport over application and adapter services:

- `GET/POST/PATCH /projects`, project archive operations
- `GET/POST /projects/{project_uid}/documents`, upload and ingestion retry
- `GET/POST/PATCH/DELETE /projects/{project_uid}/sessions`
- `GET /projects/{project_uid}/sessions/{session_uid}/messages`
- `POST /projects/{project_uid}/sessions/{session_uid}/runs`
- `GET /runs/{run_uid}` and `GET /runs/{run_uid}/events?afterSeq=N`
- `GET/PUT /settings`

The local deployment resolves `X-User-Id` to `local-user` by default. The transport
must preserve project/user ownership checks. Agent turns return structured answer,
trace, delegation, evidence, plan, Todo, and human-request data; UI never infers
Agent behavior from keywords.

## Conversation run protocol

Agent work uses HTTP commands plus a durable SSE event stream. Creating a Run is
idempotent through `client_request_id`, persists the user message immediately, and
returns before model execution begins. The background worker records canonical
events with `eventId`, a monotonic per-Run `sequence`, timestamp, type, and payload.
The client folds `run.*`, `plan.updated`, `tool.*`, and `agent.*` events into a
compact execution timeline and exposes the full public trace in the inspector.
It applies events by per-Run sequence, buffers a short out-of-order arrival, and
ignores replayed sequences. A live answer is one Assistant message made of
Markdown, activity, citation, and A2UI parts - never a separate Agent chat room.

While a Run is active, the conversation shows one low-emphasis, collapsible
activity summary inside the Assistant message. Its data is projected on the server from
actual tool lifecycle hooks: queued/started/completed/failed Runs, `write_todos`
plan updates, tool names with sanitized inputs and outputs, and task-tool based
subagent lifecycle. It must not infer model intent from event text, present
invented progress tips, or label execution telemetry as hidden model reasoning.
Provider reasoning is rendered only when a provider supplies an explicit,
user-displayable reasoning part; PaperSage currently does not request or persist
such parts.

Assistant content is rendered by AI Elements `MessageResponse`, with Markdown,
code blocks, CJK, and KaTeX math. PaperSage keeps the durable Run protocol as its
canonical transport rather than forcing it into an AI SDK provider stream; AI SDK
and AI Elements own rendering and message-part affordances at the React boundary.
Machine-readable `<evidence>`
tags are converted into inline citation controls; raw protocol tags must never be
shown to users. A turn stores cited
evidence separately from all retrieved candidates so the inspector can distinguish
grounding actually used in the answer from retrieval context that was considered.
Both `search_document` and sequential `read_document` return the same citeable
evidence schema.

A provider response containing neither visible text nor tool calls is invalid. The
model middleware retries it; exhaustion fails the Run with a user-safe error event.
The backend must never convert an empty provider response into a synthetic Assistant
answer or persist the Run as successful.

SSE subscriptions accept `afterSeq` for ordered replay. The Run and its events live
in SQLite independently of the browser connection, so a disconnected client does
not own task execution. The older synchronous `/turns` endpoint remains only as a
compatibility API; the React application must use the Run protocol.

The Run stream also carries `message.part.delta` events produced from LangGraph's
`messages` stream mode. The client renders those parts immediately and replays
them from sequence zero when reopening a session with a queued or running Run.
The final `run.completed` event remains the authoritative persisted answer; a
stream which has begun but cannot provide a final graph state fails rather than
executing the Agent a second time.

## Runtime and delivery

`make run` (or its `make dev` alias) runs API and Vite concurrently. Production builds `web/dist` and `make serve` starts FastAPI

## A2UI knowledge structures

Mind maps use a restricted A2UI v0.9 catalog rather than HTML or model-authored UI. The server validates and persists the ordered `createSurface`, `updateComponents`, and `updateDataModel` envelopes. The browser replays those envelopes in order and accepts only PaperSage's `Mindmap` root component and `/mindmap` data path. Reconnecting to an active run replays the same persisted events, so the visible answer, activity timeline, and knowledge structure recover together.
serves it with SPA fallback. Streamlit modules and tests are removed; API contract,
React unit, TypeScript, lint, and production-build checks replace them.

## Local browser verification

On Windows, use `make browser-cdp` before browser-driven verification. It starts an
isolated headless Chrome on CDP port `9223`, avoiding Chrome's unreliable dynamic
`DevToolsActivePort` launch path. Connect once with `agent-browser connect 9223`,
then use normal `agent-browser open`, `snapshot`, and `screenshot` commands.
