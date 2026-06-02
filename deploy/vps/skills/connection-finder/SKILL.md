---
name: connection-finder
description: Surface non-obvious links between this-week notes and older hubs using obsidian-graph MCP graph operations. Weekly job. Writes to outputs/analyses/.
---

# Connection Finder

Find links that are semantically real but not yet wikilinks in the vault. Use the graph, not naive search.

## Inputs

1. All notes in `wiki/concepts/`, `wiki/entities/`, `wiki/sources/`, `wiki/synthesis/` modified in last 7 days
2. Hub list via `mcp_obsidian-graph_get_hub_notes` (limit 15)
3. Orphan list via `mcp_obsidian-graph_find_orphans`

## Process

1. List recently-modified notes (last 7 days).

2. For each recent note:
   a. `mcp_obsidian-graph_get_outlinks(note)` — what it already links to
   b. `mcp_obsidian-graph_trace_concept` on each key term in the note title and frontmatter
   c. Compare trace results against existing outlinks → set difference = link candidates
   d. For each candidate, `mcp_obsidian-graph_find_path(recent_note, candidate)` — if path length > 2 or no path, this is a non-obvious connection worth surfacing

3. For each candidate connection, classify:
   - **Strong**: candidate appears in the recent note's body text OR shares 3+ keywords
   - **Moderate**: candidate shares 1–2 keywords AND both are hubs or near-hubs
   - **Weak**: distant overlap — DROP

4. Drop Weak. Drop candidates already linked. Drop trivial connections (same folder, near-identical titles).

5. Special pass: orphans. For each orphan in the recent week, attempt to find at least one Strong/Moderate connection. If found, flag as "orphan rescue."

6. Generate report:

```markdown
---
type: connection-report
date: <YYYY-MM-DD>
generated_by: connection-finder skill
range: last 7 days
---

# Connection Report — <YYYY-MM-DD>

## Summary
<N> connections found across <N> notes. <N> orphan rescues.

## Strong Connections
### [[<recent-note>]] ↔ [[<candidate>]]
- **Reason**: <specific shared concepts/terms>
- **Suggested link text**: <how to phrase the wikilink in context>
- **Where to add**: <section of recent note where this fits>

<repeat>

## Moderate Connections
<same structure>

## Orphan Rescues
### [[<orphan>]] → [[<hub>]]
<reason + suggested link>
```

7. Save to: `outputs/analyses/<YYYY-MM-DD>-connections.md`

8. Append to `outputs/ingest-log.md`.

## Quality Bar

- Only surface non-obvious. If both notes are already 1-hop apart in the graph and connection is from titles alone, drop.
- Every suggestion must name the exact wikilink to add and where to add it.
- Skip duplicates of last week's report — read `outputs/analyses/<prev-week>-connections.md` and exclude already-suggested pairs.

## Failure Modes

- If no notes modified in last 7 days → write a one-line report saying so. Do not invent.
- If MCP unavailable → abort, log, exit non-zero (this skill is graph-dependent).
