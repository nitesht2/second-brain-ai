# Second Brain AI

An automated personal knowledge base built on Obsidian + Claude Code + local LLMs. Clip anything from the web, and your Second Brain processes it into a connected knowledge graph automatically — no manual effort, no cloud costs for the daily pipeline.

> Inspired by [swyx's brain](https://github.com/swyxio/brain) and the Karpathy LLM-Wiki pattern. Built with Claude Code.

---

## What It Does

1. **You clip** an article, tweet thread, or video transcript using the Obsidian Web Clipper
2. **It lands** in your `raw/` folder automatically
3. **Every 2 days at 4am**, a local LLM (Gemma 3 via Ollama — free, no API key) processes the clips into structured wiki entries with `[[wikilinks]]`
4. **You open Obsidian** and see new nodes already connected in your knowledge graph

For deep research and important clips, run `/second-brain-ingest` in Claude Code for full Claude Sonnet quality.

---

## Architecture

```
Web Clipper (Chrome)
      ↓
~/SecondBrain/raw/          ← raw clips land here
      ↓
auto_ingest.py              ← runs every 2 days at 4am via launchd (free, local LLM)
      ↓
~/SecondBrain/wiki/
   ├── entities/            ← people, companies, tools (one file each)
   ├── concepts/            ← ideas, frameworks, strategies
   └── sources/             ← one summary per raw clip
      ↓
Obsidian Graph View         ← visual knowledge graph via [[wikilinks]]
      ↓
/second-brain-query         ← ask questions, get cited answers
```

---

## Features

- **Zero-cost daily pipeline** — local Gemma 3 / Qwen 3.5 via Ollama, no API fees
- **Claude Code slash commands** — `/second-brain-ingest`, `/second-brain-query`, `/second-brain-lint`
- **Auto-scheduler** — macOS launchd fires every 2 days at 4am, catches up if Mac was asleep
- **Lint health checks** — detects broken wikilinks, orphaned notes, stubs, and connection gaps
- **Hybrid quality** — use local LLM for routine clips, Claude Sonnet for important research
- **Obsidian-native** — all wiki entries are plain Markdown with `[[wikilinks]]`, works with graph view

---

## Prerequisites

- **macOS** (launchd scheduler is macOS-only)
- **[Obsidian](https://obsidian.md)** — free desktop app
- **[Ollama](https://ollama.com)** — free local LLM runtime
- **[Claude Code](https://claude.ai/code)** — for slash commands (optional but recommended)
- **[Obsidian Web Clipper](https://obsidian.md/clipper)** — Chrome/Firefox extension

---

## Setup

### 1. Create your vault

```bash
mkdir -p ~/SecondBrain/{raw/processed,wiki/{entities,concepts,sources},outputs}
```

Or copy the `vault-template/` folder from this repo as your starting structure.

Open Obsidian and point it to `~/SecondBrain/` as a new vault.

### 2. Install Ollama and pull a model

```bash
# Install Ollama from https://ollama.com
ollama pull gemma3:4b        # fast, good structured output (~3GB)
# or
ollama pull qwen3.5:9b       # higher quality (~7GB), uses 'thinking' field
```

### 3. Set up the Web Clipper

1. Install [Obsidian Web Clipper](https://obsidian.md/clipper) in Chrome
2. Open the extension settings
3. Set **Note location** to `raw`
4. Name your template (e.g. "Brain Dump")
5. Clip any webpage — it will land in `~/SecondBrain/raw/`

### 4. Install Claude Code slash commands (optional)

Copy the commands to your Claude Code commands directory:

```bash
cp claude-commands/*.md ~/.claude/commands/
```

Available commands:
- `/second-brain-ingest` — process all raw clips using Claude Sonnet (best quality)
- `/second-brain-query [question]` — search your wiki and get a cited answer
- `/second-brain-lint` — health check: broken links, orphans, stubs, gaps

### 5. Set up auto-ingest (local LLM, free)

**Edit the plist** to match your Python path:

```bash
which python3    # copy this path
```

Open `launchd/com.nitesh.secondbrain-ingest.plist` and update the Python path if needed (default is `/opt/homebrew/bin/python3`).

**Install and activate:**

```bash
cp auto_ingest.py ~/SecondBrain/
cp launchd/com.nitesh.secondbrain-ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
```

**Verify it loaded:**

```bash
launchctl list | grep secondbrain
# Should show: -  0  com.nitesh.secondbrain-ingest
```

The script runs every 2 days at 4:07am. If your Mac was asleep, it runs the moment you open it.

### 6. Test the pipeline

```bash
# Add a test clip
echo "# Test Note\nGemma 3 is Google's open-source model family. Runs locally via Ollama." > ~/SecondBrain/raw/test.md

# Dry run (no writes)
python3 ~/SecondBrain/auto_ingest.py --dry-run

# Real run
python3 ~/SecondBrain/auto_ingest.py
```

Check `~/SecondBrain/wiki/` for generated entries and `~/SecondBrain/outputs/ingest-log.md` for the run log.

---

## Usage

### Clip anything

Use the Web Clipper extension to save articles, tweet threads, research papers, YouTube transcripts — anything. They land in `raw/` and get processed automatically.

### Ask questions

```
/second-brain-query What is the best strategy to grow on LinkedIn?
```

Claude searches your entire wiki, synthesizes an answer with citations, and saves it to `outputs/`.

### Run a health check

```
/second-brain-lint
```

Outputs a report with:
- Broken wikilinks
- Orphaned notes (fewer than 2 links)
- Stub entries to expand
- Missing entries referenced across the wiki
- Suggested new connections

### Manual ingest (Claude Sonnet quality)

```
/second-brain-ingest
```

For important clips where you want Claude's full reasoning and connection-making ability. Uses Claude Code tokens — save this for research that matters.

---

## File Structure

```
second-brain-ai/
├── auto_ingest.py                    # local LLM ingest script
├── launchd/
│   └── com.nitesh.secondbrain-ingest.plist   # macOS scheduler (every 2 days, 4am)
├── claude-commands/
│   ├── second-brain-ingest.md        # /second-brain-ingest slash command
│   ├── second-brain-query.md         # /second-brain-query slash command
│   └── second-brain-lint.md          # /second-brain-lint slash command
└── vault-template/                   # empty vault structure to copy
    ├── raw/
    │   └── processed/
    ├── wiki/
    │   ├── entities/
    │   ├── concepts/
    │   └── sources/
    └── outputs/
```

---

## Configuration

Edit the config section at the top of `auto_ingest.py`:

```python
MODEL       = "gemma3:4b"    # swap to qwen3.5:9b for higher quality
MIN_HOURS   = 48             # hours between auto-ingest runs (48 = every 2 days)
MAX_TOKENS  = 3000           # max tokens per model response
RAW_CHUNK   = 3500           # chars of each clip fed to the model
```

To change the schedule (e.g. run every day instead of every 2 days):

```python
MIN_HOURS = 24
```

---

## Local LLM vs Claude Sonnet

| | Auto-ingest (local) | `/second-brain-ingest` (Claude) |
|---|---|---|
| Cost | Free | Claude Code tokens |
| Model | gemma3:4b / qwen3.5 | Claude Sonnet |
| Quality | Good — structure + basic links | Excellent — deep connections |
| Speed | ~30-60s per clip | ~10-20s per clip |
| Best for | Daily clips, tweets, bookmarks | Key research, deep articles |

**Recommended workflow:** Let local LLM handle the daily drip. Run Claude manually for anything important.

---

## How the Wiki Works

Every entry is a plain Markdown file with `[[wikilinks]]`. Obsidian renders these as edges in the graph view — the more connections, the richer your knowledge map.

**Three tiers:**
- `wiki/entities/` — people, companies, tools (e.g. `Andrej Karpathy.md`, `OpenClaw.md`)
- `wiki/concepts/` — ideas and frameworks (e.g. `Vibe Coding.md`, `Multi-Agent Systems.md`)
- `wiki/sources/` — one summary per raw clip (e.g. `LinkedIn 1 Million Followers Guide.md`)

**Rule:** Every wiki entry must have at least 2 `[[wikilinks]]`. This is enforced by the lint command.

---

## Troubleshooting

**Script says "Ollama not reachable"**
Open the Ollama app first, or run `ollama serve` in a terminal.

**launchd job not firing**
```bash
launchctl list | grep secondbrain    # check it's loaded
cat ~/SecondBrain/outputs/ingest-daemon.log   # check for errors
```

**Model output has no FILE blocks**
The model didn't follow the output format. Try switching to `gemma3:4b` (most reliable) or simplify the prompt by reducing `RAW_CHUNK`.

**qwen3.5 returns empty response**
This is expected — qwen3 is a thinking model. The script automatically falls back to the `thinking` field. No action needed.

---

## Credits

Built by [@NiteshTechAI](https://x.com/NiteshTechAI)

Inspired by:
- [swyx's brain](https://github.com/swyxio/brain) — public Obsidian vault
- Andrej Karpathy's LLM-Wiki pattern
- [Ruben Hassid](https://ruben.substack.com) — AI productivity workflows
- [Hermes Agent](https://github.com/david-gilbertson/hermes) — multi-agent knowledge base system

---

## License

MIT — free to use, modify, and share. If you build something cool with it, tag [@NiteshTechAI](https://x.com/NiteshTechAI) on X.
