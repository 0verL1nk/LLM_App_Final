# PaperSage

PaperSage is a project-oriented workspace for paper reading, evidence retrieval, and multi-agent research. Its independent Vite React client talks to a FastAPI boundary. Document extraction, OCR, embeddings, and long-term memory consolidation run asynchronously and never block session creation.

## Capabilities

- Project workspaces unify documents, sessions, evidence, and research activity.
- A Leader delegates to researcher, reviewer, and writer subagents through observed tool calls.
- Full document indexes persist in LanceDB with native dense + FTS + RRF hybrid retrieval.
- Uploads expose real extraction, OCR, embedding, publishing, ready, and failure progress.
- Completed turns enqueue model-driven long-term memory consolidation.
- Slash commands in the chat input cover `/skills`, `/compact` history summarization, `/documents`, `/memory`, `/model`, `/new`, `/rename`, `/help`, and explicit `/skill-name task` invocations.
- SQLite persists workspace state while LangGraph checkpoints persist Agent execution state.

## Stack

The `web/` client uses Vite, React, TypeScript, Tailwind CSS, shadcn/ui, Radix UI, TanStack Query, TanStack Router, Zustand, React Hook Form, Zod, and Lucide React.

The `api/` and `agent/` backend uses FastAPI, LangChain/LangGraph, Deep Agents, SQLite, LanceDB, FastEmbed, RapidOCR, and RQ/Redis.

## Development

Requires Python 3.11+, uv, Node.js 22+, and pnpm (managed through Corepack).

```bash
make install-dev
make web-install
make dev              # API :8000 and Vite :5173
```

Production:

```bash
make web-build
make run              # FastAPI serves web/dist on :8000
```

Quality gates:

```bash
make web-lint
make web-typecheck
make web-test
make web-build
make test-all
make quality-full
```

See [docs/architecture/web-application.md](docs/architecture/web-application.md) for the information architecture and API contract.
