# Wiki Schema

> Agent-facing schema for the llm-wiki skill. Defines how the agent must write
> this vault. Human-facing companion: `../AGENTS.md`. When the two ever disagree,
> AGENTS.md wins — update this file to match.

## Domain

Nitesh's working knowledge base. Topics span: AI tools & agents, data engineering
& analytics (BigQuery, Alteryx, SQL, dbt), marketing & growth, content creation
(Twitter/X, YouTube, TikTok), automation, Python/JS development, and algorithmic
trading. The vault exists to compound what he learns into a queryable, interlinked
graph he reads in Obsidian and queries via the Hermes secondbrain-agent.

## Layout (DIFFERS from llm-wiki defaults — follow THIS)

`WIKI_PATH` = the `wiki/` directory. Raw sources live in a SIBLING `../raw/`, not
under the wiki.

```
wiki/                      <- WIKI_PATH
├── SCHEMA.md              <- this file
├── index.md              <- content catalog, updated every ingest
├── log.md                <- append-only chronological action log
├── entities/             <- people, companies, tools, models (one file each)
├── concepts/             <- ideas, frameworks, strategies
├── sources/              <- one summary per ingested source
├── synthesis/            <- cross-topic patterns ("Synthesis - <Theme>.md")
├── episodic/             <- agent session records
└── projects/             <- synced from project docs

../raw/                    <- SIBLING of wiki/, immutable sources
├── *.md *.txt *.pdf       <- drop zone
├── processed/             <- ingested files (moved here after ingest)
└── generated/             <- daily digests, lint reports
```

Do NOT create `comparisons/` or `queries/` folders (llm-wiki defaults). Filed
query results go in `synthesis/` or `concepts/`. Comparisons go in `concepts/`.

## Conventions (match the existing 376 files — do not reformat them)

- **Filenames: Title Case with spaces**, e.g. `Meta Ads Lead Gen Framework.md`.
  NOT lowercase-hyphen. This matches the entire existing vault.
- Every wiki page has YAML frontmatter (see formats below).
- Use `[[wikilinks]]`. **Minimum 2 outbound links per page** (hard rule).
- **Append, never overwrite.** If a page exists, add new info and bump dates.
  Prefer linking to an existing entry over creating a near-duplicate.
- **Check before creating.** Read index.md + `search_vault`/`search_files` for the
  entity/concept first. The vault already has 376 pages — duplicates are the main
  failure mode. (This is why the old script created "Claude Design" 10x — don't.)
- Never modify files in `../raw/` — sources are immutable. Corrections go in wiki pages.
- Every new/updated page: add to `index.md` (correct section, alphabetical) and
  append a `log.md` entry.

## Frontmatter

### concepts/ and entities/ — Evergreen format (REQUIRED, from AGENTS.md)

```yaml
---
confidence: high | medium | low
explored: false
---
```
Body MUST follow:
```
# Note Title

**Date:** YYYY-MM-DD
**Tags:** #topic
**Related:** [[Link]] · [[Link]]

---

## The Idea
One clear statement, written to explain it to yourself in 12 months.

## Why It Matters
Why it matters now; what it changes about how Nitesh works/thinks. MUST reference
a specific project, goal, or decision — no generic statements.

## Counter-arguments
- At least one. What might the source miss? What would a skeptic push back on?

## Connections
- [[Related Note]]  (>= 2)
- What question does this open up?
```
Rule: if you can't fill "Why It Matters" with something specific, DON'T create the note.

### sources/ — lighter frontmatter

```yaml
---
title: "Source Title"
source: <url or origin>
created: YYYY-MM-DD
tags: [...]
---
```

## Tag Taxonomy (add new tags here before using)

ai, ai-agents, llm, automation, data-engineering, analytics, bigquery, sql,
marketing, growth, content, twitter, youtube, tiktok, python, javascript,
trading, productivity, business, tooling, prompt-engineering.

## Page Thresholds

- Create a page when an entity/concept appears in 2+ sources OR is central to one.
- Add to an existing page for anything already covered.
- Don't create pages for passing mentions.
- Split pages over ~200 lines.

## Update Policy

When new info conflicts with an existing page: check dates (newer usually wins);
if genuinely contradictory, note both with dates + sources and flag for the human.
Never silently overwrite.

## Automated Context

Ingest/lint/synthesis are run AGENTICALLY by the Hermes secondbrain-agent via this
skill (not the old auto_ingest.py script). In automated/cron runs, skip the
"discuss takeaways with the user" step and proceed directly. Queries arrive via
Discord; file substantial answers back into `synthesis/`.
