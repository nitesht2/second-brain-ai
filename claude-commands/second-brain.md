# Second Brain: Setup

Run the guided setup wizard for a new Second Brain vault.

**Vault:** `~/SecondBrain/`

## Instructions

Welcome! This wizard sets up your Second Brain vault from scratch.

### Step 1 — Create vault structure

Run:
```bash
mkdir -p ~/SecondBrain/{raw/processed,wiki/{entities,concepts,sources,synthesis},outputs}
```

Then create these starter files:
- `~/SecondBrain/wiki/index.md` — master index (auto-updated by ingest)
- `~/SecondBrain/wiki/log.md` — ingest change log
- `~/SecondBrain/CLAUDE.md` — vault instructions for Claude

### Step 2 — Verify Obsidian

Ask the user:
- "Have you opened ~/SecondBrain as a vault in Obsidian yet?"
- If no: instruct them to open Obsidian → "Open folder as vault" → select ~/SecondBrain

### Step 3 — Verify Web Clipper

Ask the user:
- "Do you have the Obsidian Web Clipper Chrome extension installed?"
- If no: direct them to https://obsidian.md/clipper
- If yes: confirm their template saves to the `raw` folder

### Step 4 — Check Ollama (for auto-ingest)

Run:
```bash
ollama list 2>/dev/null | head -5
```

- If Ollama has models: confirm `gemma3:4b` or `qwen3.5:4b` is available
- If not installed: tell user to install from https://ollama.com and run `ollama pull gemma3:4b`

### Step 5 — Install slash commands

Check if commands exist:
```bash
ls ~/.claude/commands/second-brain*.md 2>/dev/null
```

If missing, tell the user to copy from the repo:
```bash
cp claude-commands/*.md ~/.claude/commands/
```

### Step 6 — Summary

Report what was set up, what's ready, and what still needs action. Tell the user:
- Drop files in `~/SecondBrain/raw/` to add knowledge
- Run `/second-brain-ingest` to process them with Claude (best quality)
- Or run `python3 ~/SecondBrain/auto_ingest.py` for free local LLM processing
- Run `/second-brain-query [question]` to search your wiki
- Run `/second-brain-lint` for health checks
