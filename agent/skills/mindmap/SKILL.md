---
name: mindmap
description: Organize document evidence into a concise, catalog-backed research map.
---

# Mindmap Skill

## When to use this skill

Use this skill when the user asks for a mind map, concept map, or a hierarchy is materially easier to understand than linear prose. Do not generate a map solely because a topic has many points.

## Build from evidence

1. Retrieve evidence from the current project before drafting nodes.
2. Use section structure, claims, methods, results, and limitations as candidates.
3. Keep the root focused and first-level branches parallel in granularity.
4. Keep labels concise; merge duplicate or overlapping branches.
5. Attach only chunk IDs returned by this turn's document tools as `citation_ids`. Do not invent document locations.

## Present naturally

Call `present_research_surface` with a concise title and rooted hierarchy only when the map improves understanding. The surface is an optional supplement, not the answer itself.

After the tool call, write a normal Markdown response that explains the main takeaway, limitations, and the relevant `<evidence>` citations. Never emit A2UI JSON, Mermaid, HTML, JavaScript, SVG, CSS, or arbitrary component names in user-facing text.

## Quality checks

- Use two to four useful levels; avoid one branch dominating all detail.
- Omit unsupported nodes rather than guessing.
- If a map adds no value, answer in Markdown without calling the presentation tool.
