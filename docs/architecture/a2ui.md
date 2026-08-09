# A2UI presentation boundary

PaperSage uses A2UI as an optional presentation layer inside a research answer. It is not a chain-of-thought display, an alternative answer channel, or a way for a model to run browser code.

## Current contract

The system prompt automatically describes the registered presentation catalog. The model writes ordinary Markdown and may insert an own-line XML fragment such as `<ui type="research-map">…</ui>` when a compact hierarchy improves understanding. It never calls a UI tool and never emits A2UI JSON.

The server incrementally removes the private fragment from the token stream. Markdown outside it becomes durable `message.part.delta` events; the opening tag creates `message.part.insert`; after the closed XML subtree passes validation, the server compiles it to stable A2UI v0.9.1 envelopes and emits `ui.a2ui`. Thus text before and after a map remains visible while the map is prepared in place.

Each map node may contain `citation_ids`, but the server retains only chunk IDs retrieved during the same turn. A click opens the existing Evidence Inspector; it does not let model-provided URLs or code reach the client.

## Trust and resource boundaries

- Only the local `Mindmap` catalog and `/mindmap` data path are accepted.
- The server limits label length, child count, depth, node count, title length, and citations per node.
- React receives validated data only. It does not execute HTML, JavaScript, CSS, SVG, arbitrary actions, or model-provided URLs.
- Invalid surface input falls back to the normal answer; it never replaces it.

## Recovery and evolution

Run events have a durable, increasing sequence number. The client replays them in order after reconnecting and keeps surfaces by `surfaceId` and message part ID, so a completed or in-flight map can recover independently without re-parsing model text. `deleteSurface` removes only its matching surface.

Additional catalogs such as comparison matrices or timelines must remain evidence-grounded and must not expose generic renderer capabilities to the model.

References: [A2UI specification](https://a2ui.org/specification/v0.9-a2ui/), [catalog guidance](https://a2ui.org/guides/defining-your-own-catalog/), and [renderer guidance](https://a2ui.org/guides/renderer-development/).
