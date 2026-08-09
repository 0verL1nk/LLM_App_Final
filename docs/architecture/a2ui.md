# A2UI presentation boundary

PaperSage uses A2UI as an optional presentation layer for a completed research answer. It is not a chain-of-thought display, an alternative answer channel, or a way for a model to run browser code.

## Current contract

The leader may call `present_research_surface` when a compact hierarchy materially improves understanding. The tool accepts a bounded research map only; the server validates it, builds catalog-backed envelopes compatible with the stable A2UI v0.9.1 specification, persists them beside the assistant message, and emits them as `ui.a2ui` run events. Each event includes the validated surface identity and title, while the envelope itself remains protocol-only.

The model must still return normal Markdown and `<evidence>` citations. Streamed deltas contain only that user-facing answer: the renderer never parses A2UI from model text.

Each map node may contain `citation_ids`, but the server retains only chunk IDs retrieved during the same turn. A click opens the existing Evidence Inspector; it does not let model-provided URLs or code reach the client.

## Trust and resource boundaries

- Only the local `Mindmap` catalog and `/mindmap` data path are accepted.
- The server limits label length, child count, depth, node count, title length, and citations per node.
- React receives validated data only. It does not execute HTML, JavaScript, CSS, SVG, arbitrary actions, or model-provided URLs.
- Invalid surface input falls back to the normal answer; it never replaces it.

## Recovery and evolution

Run events have a durable, increasing sequence number. The client replays them in order after reconnecting and keeps surfaces by `surfaceId`, so a completed or in-flight map can recover independently without re-parsing model text. `deleteSurface` removes only its matching surface.

The next migration adopts a generic A2UI v0.9.1 renderer for additional catalogs, incremental updates, replay snapshots, and catalog versioning. Future catalog entries such as comparison matrices or timelines must remain evidence-grounded and must not expose generic renderer capabilities to the model.

References: [A2UI specification](https://a2ui.org/specification/v0.9-a2ui/), [catalog guidance](https://a2ui.org/guides/defining-your-own-catalog/), and [renderer guidance](https://a2ui.org/guides/renderer-development/).
