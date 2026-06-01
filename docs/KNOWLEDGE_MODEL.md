# Knowledge model

The agent doesn't dump unstructured text. Every wiki page follows a schema
designed for compounding knowledge over time.

Full machine-readable schema: [`../deploy/vps/SCHEMA.template.md`](../deploy/vps/SCHEMA.template.md).

## Page anatomy

Concept and entity pages carry frontmatter that captures both content and provenance:

```yaml
---
confidence: high | medium | low
explored: false
valid_from: YYYY-MM-DD       # when the claim became true in the world
learned_on: YYYY-MM-DD       # when this vault first recorded it
last_verified: YYYY-MM-DD    # last time a re-ingest confirmed the claim
superseded_by: [[New Page]]  # optional — set when a newer claim replaces this
contradicts: [[Other Page]]  # optional — set when two pages disagree
sources: [path/to/source.md, ...]
---
```

The body follows an evergreen-note structure:

```
# Page Title

## The Idea
One clear statement, written to be useful 12 months from now.

## Why It Matters
What it changes about how the reader works or thinks. Specific, not generic.

## Counter-arguments
At least one. What might the source be missing? What would a skeptic say?

## Connections
- [[Related Page A]]
- [[Related Page B]]
- An open question this opens up.
```

This format forces the agent to write notes that hold up over time — not
stream-of-consciousness summaries that read fine today and are noise next year.

## Three patterns that differentiate this from a notes app

### 1. Bi-temporal facts

Each page tracks *when something was true in the world* (`valid_from`) separately
from *when the vault learned it* (`learned_on`).

Example: a 2024 fact ingested in 2026 has `valid_from: 2024, learned_on: 2026`.

This unlocks two capabilities a single-date system can't have:

- **Time-travel queries** — "what did I know about X as of last March?"
- **Drift detection** — if `last_verified` is more than 180 days old, the next
  mention of the topic triggers a re-check on next ingest. Stale knowledge surfaces
  itself instead of silently rotting.

### 2. Contradiction auto-resolve

When a new source disagrees with an existing page, the agent doesn't shrug and
flag it for you. It executes a deliberate resolution:

1. Compare `valid_from` dates (newer usually wins for time-sensitive facts).
2. Compare source count and confidence (a single 2026 source doesn't override
   five 2024 sources for timeless ideas).
3. Pick a winner, rewrite the page with the resolved claim.
4. Move the loser content to a `## Superseded` section at the bottom with date
   and reason ("Replaced 2026-06-01 by [[New Source]]: X now does Y, was Z").
5. Stamp the loser page's frontmatter with `superseded_by:` pointing to the winner.
6. Log the change to `log.md` so the trail is auditable.

Only when the conflict is genuinely context-dependent (two valid strategies, two
opinions) does the agent keep both pages alive and link them via `contradicts:`
cross-references. The weekly lint surfaces those for human review.

The old "flag and move on" pattern lets contradictions pile up. Letting the agent
resolve them in place is the upgrade.

### 3. Decision Records (ADRs)

When the agent helps you pick between real alternatives — which tool, which
architecture, which strategy — it writes a lightweight ADR to `wiki/decisions/`
capturing:

- Context (what forced the call)
- Options considered (with pros/cons each)
- Choice + reasoning
- Trade-offs / consequences
- **Revisit when** — a concrete trigger (e.g. "if monthly cost > $20")

Future-you can answer "why did I build it this way?" months later. They also
double as raw material for "build in public" content — every ADR is one tweet's
worth of receipts.

ADRs are only written for non-trivial choices (skip "which folder name"); the
agent decides based on whether the choice has 2+ real alternatives and would
matter in 6 months.

### 4. Bonus: graphify bridge

If your projects use [graphify](https://github.com/.../graphify) (or any AST-graph generator), the
agent reads `graphify-out/GRAPH_REPORT.md` *before* grepping source files. Code
architecture questions get answered from the pre-built graph instead of
reconstructing the picture from raw files every time. Far cheaper in tokens, far
more accurate.

## Vault layout

```
SecondBrain/
├── raw/                ← drop zone (immutable sources)
│   ├── processed/      ← ingested files, moved here after processing
│   └── generated/      ← daily digests, lint reports
└── wiki/               ← agent-maintained — never edit by hand mid-session
    ├── SCHEMA.md       ← the rules the agent follows
    ├── index.md        ← auto-updated content catalog
    ├── log.md          ← append-only chronological action log
    ├── entities/       ← people · companies · tools · models
    ├── concepts/       ← ideas · frameworks · strategies
    ├── sources/        ← one summary per ingested source
    ├── synthesis/      ← cross-topic patterns ("Synthesis - <Theme>.md")
    ├── decisions/      ← ADRs (auto-written for non-trivial choices)
    ├── episodic/       ← agent session records
    └── projects/       ← synced from project documentation
```

This is a regular Obsidian vault. `[[wikilinks]]` resolve correctly, the graph
view works out of the box, Dataview queries run normally. If the agent stops
running tomorrow, the vault is still readable and editable by hand.
