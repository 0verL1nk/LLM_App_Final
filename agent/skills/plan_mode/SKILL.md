---
name: plan_mode
description: Revisioned planning mode for complex multi-step tasks.
---

# Plan Mode

Use planning only when a task has meaningful dependencies, parallel lanes, or
several independently checkable outcomes. Simple requests should proceed directly.

## Workflow

Create one complete plan snapshot with `update_plan(revision=0, goal, steps)`. Each
step has an explicit `id`, `title`, `status`, optional `depends_on`, `lane`, and
`task_uid`. After substantive progress, call `update_plan` again with the next
revision and the full updated step list.

Example:

```text
update_plan(
  revision=0,
  goal="Research and compare LLM frameworks",
  steps=[
    {id: "search", title: "Find primary sources", status: "in_progress"},
    {id: "extract", title: "Extract comparable features", depends_on: ["search"]},
    {id: "compare", title: "Compare tradeoffs", depends_on: ["extract"]}
  ]
)
```

Use `read_plan` before revising when the current revision is unknown. Mark completed,
blocked, or failed steps in the next revision; do not maintain a parallel Todo list.
Each final factual claim still needs evidence, and unresolved evidence gaps must be
made explicit.

## Available tools

- `update_plan` — atomically replace the next revisioned snapshot
- `read_plan` — inspect the current snapshot
- `search_document`, `search_papers`, `search_web` — gather evidence
- `use_skill` — apply a domain skill
