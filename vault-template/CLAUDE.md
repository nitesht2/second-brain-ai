# Second Brain Vault — Claude Instructions

This is my personal knowledge base vault. When running commands in this vault:

## Vault Structure
- `raw/` — unprocessed clips, articles, transcripts. NEVER edit these directly.
- `raw/processed/` — clips that have been ingested. Don't touch.
- `wiki/entities/` — one file per person, company, or tool.
- `wiki/concepts/` — one file per idea, framework, or strategy.
- `wiki/sources/` — one summary file per raw clip.
- `wiki/synthesis/` — cross-topic insights connecting multiple concepts.
- `outputs/` — query results and lint reports.

## Rules
- Every wiki entry must have at least 2 `[[wikilinks]]`
- Use Title Case for all wiki filenames
- Never delete raw files — move to raw/processed/ after ingesting
- If a wiki entry already exists, append new info rather than overwriting
- Wikilinks should prefer linking to existing entries over creating new ones

## Commands
- `/second-brain-ingest` — process all files in raw/
- `/second-brain-query [question]` — search and synthesize an answer
- `/second-brain-lint` — health check the wiki
