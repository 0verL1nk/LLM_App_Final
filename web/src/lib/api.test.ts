import { afterEach, describe, expect, it, vi } from "vitest"

import { consumeEventStream } from "@/lib/api"

afterEach(() => vi.unstubAllGlobals())

describe("consumeEventStream", () => {
  it("reassembles split SSE frames and ignores heartbeats", async () => {
    const encoder = new TextEncoder()
    const chunks = [
      'id: evt_1\nevent: run.started\ndata: {"sequence":1,',
      '"eventType":"run.started"}\n\n: ping\n\n',
      'id: evt_2\nevent: step.progress\ndata: {"sequence":2,"eventType":"step.progress"}\n\n',
    ]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
        controller.close()
      },
    }), { status: 200, headers: { "Content-Type": "text/event-stream" } })))
    const events: unknown[] = []

    await consumeEventStream("/api/v1/runs/run-1/events", (event) => events.push(event))

    expect(events).toEqual([
      { sequence: 1, eventType: "run.started" },
      { sequence: 2, eventType: "step.progress" },
    ])
  })
})
