---
name: weekly-synthesis
description: Synthesize the full week's vault activity into a review that surfaces patterns invisible in any single day. Updates wiki/index.md priorities. Runs Sunday evening.
---

# Weekly Synthesis

Read the week. Produce the document you read first on Monday morning.

## Inputs

1. All `outputs/briefings/` from last 7 days
2. All `wiki/` notes (concepts, entities, sources, synthesis) created or modified in last 7 days
3. `outputs/ingest-log.md` last 7 days
4. This week's `outputs/analyses/<date>-connections.md` if exists
5. This week's `outputs/analyses/<date>-thinking-partner.md` if exists
6. Previous weekly synthesis: most recent `outputs/reviews/<prev>-weekly-synthesis.md`
7. Hub stats via `mcp_obsidian-graph_get_vault_stats` + `mcp_obsidian-graph_get_hub_notes`

## Process

1. Pull weekly metrics:
   - New notes by folder (concepts / entities / sources / synthesis)
   - Hub changes (which hubs gained/lost backlinks since last week — compare to previous synthesis's snapshot)
   - Orphans created vs orphans rescued this week

2. Identify the **one theme** that appeared most across the week's notes. Use `mcp_obsidian-graph_trace_concept` on candidate terms to verify frequency.

3. Compare to previous week's synthesis: what was promised? what was delivered? what slipped?

4. Generate:

```markdown
---
type: weekly-synthesis
date: <YYYY-MM-DD>
week_of: <YYYY-MM-DD of Monday>
generated_by: weekly-synthesis skill
---

# Weekly Synthesis — Week of <YYYY-MM-DD>

## The week in one line
<single sentence — the most important thing this week revealed>

## What moved
- <specific progress with [[note]] references>

## What did not move
- <honest assessment of stalled items + most likely reason, NOT generic>

## Ideas that emerged
- [[wiki/concepts/<new>]]: <why it matters>
<repeat for new permanent notes worth attention>

## The pattern
<one theme that appeared repeatedly. Cite the 3+ notes where it shows up>

## Connections made
<best connections from this week's connection-finder report, validated>

## Hub movement
- <hub>: <gained/lost backlinks, what this signals>

## Next week priorities
1. <specific, actionable, with first step>
2. <same>
3. <same>

## Index update
<exact diff to apply to wiki/index.md priorities section>
```

5. Save to: `outputs/reviews/<YYYY-MM-DD>-weekly-synthesis.md`

6. **Apply the index update**: open `wiki/index.md`, find the priorities section (delimited by `<!-- PRIORITIES_START -->` / `<!-- PRIORITIES_END -->` — if missing, add these markers around current priorities first), replace with next-week's top 3.

7. Append to `outputs/ingest-log.md`.

8. Deliver to Discord — full synthesis (will auto-split at 2000-char Discord limit, that's fine since paste-collapse threshold is now 6000 chars / 40 lines).

## Quality Bar

- "What did not move" must name specific stalled work, not generic. "I didn't write much" fails. "[[project-X]] last modified 9 days ago, blocked on <specific thing>" passes.
- "The pattern" must cite the 3+ notes where the theme shows up. If you can't find 3, there is no pattern this week — say so.
- Index update is the only skill that mutates the wiki directly. If `<!-- PRIORITIES_START -->` markers don't exist, ADD them rather than overwriting blind.

## Failure Modes

- No prior synthesis exists → mark as first week, skip prior-comparison section.
- Less than 3 new notes in week → still produce synthesis but flag: `low-activity week — synthesis limited`.
- MCP unavailable → degraded mode, flag in output, skip hub-movement section.
