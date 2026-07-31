---
name: mindmap
description: Generate validated A2UI mind-map surfaces from document evidence with clear hierarchy and concise node labels.
---

# Mindmap Skill

## When to use this skill

Use this skill when:
- User asks for a mind map, concept map, or knowledge structure
- User wants hierarchical decomposition of a paper
- Output must be a machine-parseable A2UI surface for visualization

## How to build the mind map

### Step 1: Ground in evidence
- Retrieve evidence from the current document before drafting nodes
- Use chapter names, section headers, or repeated key terms as candidates
- Do not invent concepts not supported by the document

### Step 2: Build hierarchy
- Root node: one concise theme for the whole paper
- First level: 3-6 major branches (problem, method, experiment, results, limitations, outlook)
- Second level: 2-4 concrete points per branch
- Keep depth between 2 and 4 levels

### Step 3: Keep labels concise
- Use short noun phrases for node names
- Avoid full sentences when possible
- Merge duplicated or overlapping branches

### Step 4: Output format
- Output exactly three A2UI v0.9 JSONL envelopes - NO markdown fences or wrapper tags
- Output only the three allowed A2UI messages, with no explanation before or after
- Never output Mermaid, HTML, JavaScript, SVG, CSS, or arbitrary component names

## Output contract

Emit exactly three JSON objects, one per line. Do not wrap them in any tag:

{"version":"v0.9","createSurface":{"surfaceId":"mindmap-1","catalogId":"https://papersage.local/a2ui/catalogs/mindmap-v1.json"}}
{"version":"v0.9","updateComponents":{"surfaceId":"mindmap-1","components":[{"id":"root","component":"Mindmap","data":{"path":"/mindmap"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"mindmap-1","path":"/mindmap","value":{"label":"主题","children":[{"label":"子主题","children":[{"label":"要点1","children":[]}]}]}}}

Invalid examples:
- `## 标题` followed by JSON
- ```mermaid ... ```
- Any wrapper tag or explanation before/after the JSONL stream

## Quality checks

- Ensure branch coverage is balanced (no single branch dominates all details)
- Ensure sibling nodes are parallel in granularity
- If evidence is insufficient, include a minimal node such as "信息不足" instead of guessing
