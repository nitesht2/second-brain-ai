---
name: morning-brief
description: Generate a vault-aware morning brief from the SecondBrain wiki. Reads index, recent log entries, hub notes, and recent syntheses via obsidian-graph MCP. Writes to outputs/briefings/ and delivers via Discord.
---

# Morning Brief

Generate a tight, vault-grounded morning brief. The brief must reference specific notes in the vault by path. No generic observations.

## Vault Location

`~/SecondBrain/` (on VPS: `/root/SecondBrain/`)

## Inputs

Read in this order, every run:

1. `wiki/index.md` — current vault state, hub list, recent activity
2. `outputs/ingest-log.md` — last 7 days of ingest entries (what came in)
3. Most recent 3 entries in `wiki/synthesis/` (most-recent-first by file mtime)
4. Top 5 hubs from `mcp_obsidian-graph_get_hub_notes` — current centers of gravity
5. Yesterday's brief if exists: `outputs/briefings/<YYY-MM-DD>-morning-brief.md`

## Process

1. Pull context via MCP tools — NOT raw file reads where MCP works:
   - `mcp_obsidian-graph_get_vault_stats`
   - `mcp_obsidian-graph_get_hub_notes` (limit 5)
   - `mcp_obsidian-graph_trace_concept` for any topic that appeared in last 3 syntheses

2. Identify:
   - **New sources** ingested in last 24h (from ingest-log)
   - **Open loops** — synthesis entries with unresolved questions or `TODO:` markers
   - **Hub drift** — hub notes modified in last 7 days (signal: focus is shifting)
   - **Stale hubs** — hubs not modified in 30+ days (signal: dormant theme)

3. Generate the brief in this exact structure:

```markdown
---
type: morning-brief
date: <YYYY-MM-DD>
generated_by: morning-brief skill
---

# Morning Brief — <YYYY-MM-DD>

## ONE THING TODAY
<single highest-leverage action grounded in vault evidence>

## NEW SINCE YESTERDAY
- <source>: [[wiki/sources/<file>]] — one-line takeaway
<repeat for each new ingest>

## OPEN LOOPS
- [[wiki/synthesis/<file>]]: <specific unresolved question>
<repeat>

## CURRENT HUBS
<top 5 hubs from MCP, each with one-line "what changed this week" if modified, else "stable">

## CONNECTION OF THE DAY
<one non-obvious link between a new ingest and an existing hub. Use find_path or get_graph_neighbors to verify the connection exists in the graph>
```

4. Save to: `outputs/briefings/<YYYY-MM-DD>-morning-brief.md`

5. Append a one-line entry to `outputs/ingest-log.md`:
   `<TIMESTAMP> | morning-brief | generated <path>`

6. Return brief content to Discord (gateway delivers).

## Quality Bar

- Every claim must reference a specific note path. No floating observations.
- "ONE THING TODAY" must be actionable, not aspirational.
- "CONNECTION OF THE DAY" must surface a link not already explicit in the notes.
- If vault has no new ingests in 24h, say so. Do not invent activity.

## Failure Modes

- If `wiki/index.md` is missing → abort, log to ingest-log, exit non-zero.
- If MCP unavailable → fall back to direct file reads but flag in brief: `[degraded mode: MCP unavailable]`.
