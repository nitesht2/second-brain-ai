# Second Brain Vault — Agent Instructions

This vault is maintained by AI agents. You read it in Obsidian. Agents write it.

## Architecture (Karpathy-style, automated)

Three layers, exactly as Karpathy described in his llm-wiki gist:

```
Raw Sources (immutable)  →  Wiki (LLM-maintained)  →  Schema (this file)
```

Every 6 hours, a heartbeat fires three phases:

### Phase 1: Distillation
Agents write session records to `episodic/` after every run. The heartbeat reads them and extracts new concepts, entities, and patterns into the wiki.

### Phase 2: Ingestion
New files in `raw/` get processed by the file watcher (fswatch) immediately, or by the cron fallback every 6 hours. Content is read, entities extracted, wiki entries created with cross-references.

### Phase 3: Project Sync
Active project CLAUDE.md and README.md files are scanned every 6 hours. Changed files get extracted into `wiki/projects/`.

## Vault Structure

```
wiki/
├── index.md              ← auto-updated by every ingest run
├── log.md                ← append-only chronological log
├── entities/             ← people, companies, tools (one file each)
├── concepts/             ← ideas, frameworks, strategies
├── sources/              ← one summary per ingested source
├── synthesis/            ← cross-topic patterns and insights
├── episodic/             ← agent session records (auto-generated)
└── projects/             ← auto-synced from project docs

raw/
├── *.md, *.txt, *.pdf    ← drop files here for ingestion
├── processed/            ← files that have been ingested
└── generated/            ← auto-generated content (digests, lint reports)

outputs/                  ← query results, lint outputs, logs
```

## Wiki Rules

- Every wiki entry must have at least 2 `[[wikilinks]]`
- Use Title Case for all wiki filenames
- Never delete raw files — move to `raw/processed/` after ingesting
- If a wiki entry exists, append new info rather than overwriting
- Prefer linking to existing entries over creating new ones
- All pages use Obsidian-flavored markdown (wikilinks, frontmatter)
- The LLM writes. You read.

## Automated Operations

| Operation | Trigger | Frequency |
|-----------|---------|-----------|
| Distillation | Hermes Agent cron | Every 6 hours |
| Ingestion | fswatch or cron fallback | Real-time + 6h fallback |
| Project sync | Hermes Agent cron | Every 6 hours |
| Daily digest | Python script | 6 AM daily |
| Weekly scans | Agent browser | Sundays 7 AM |
| Wiki lint | Agent (local vault) | Sundays after scans |

## Reference Repos

- Karpathy's llm-wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- kepano/obsidian-skills: https://github.com/kepano/obsidian-skills
