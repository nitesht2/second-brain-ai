# 🧠 Second Brain AI

> **Clip anything from the web. Wake up to a connected knowledge graph. Zero effort. Zero cost.**

An automated personal knowledge base built on **Obsidian + Claude Code + free local AI**. You save articles, tweets, and notes — the AI organizes them into a searchable, visual wiki while you sleep.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Runs%20on-Ollama-black)](https://ollama.com)
[![Claude Code](https://img.shields.io/badge/Works%20with-Claude%20Code-orange)](https://claude.ai/code)
[![Obsidian](https://img.shields.io/badge/Visualized%20in-Obsidian-7c3aed)](https://obsidian.md)
[![macOS](https://img.shields.io/badge/Scheduler-macOS%20launchd-lightgrey)](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/ScheduledJobs.html)

---

## 🎯 What This Does

You clip an article → it lands in a folder → free local AI processes it automatically every 2 days at 4am → Obsidian shows you a connected graph of everything you've learned.

```
📎 Clip article with Obsidian Web Clipper
               ↓
📁 Lands in ~/SecondBrain/raw/
               ↓
⏰ Every 2 days at 4am  (automatic, macOS launchd)
               ↓
🤖 Local AI processes each clip  (Ollama + Gemma 3, completely free)
               ↓
🗂️  Wiki entries created automatically:
    wiki/entities/   → people, companies, tools
    wiki/concepts/   → ideas, frameworks, strategies
    wiki/sources/    → one summary per clip
    wiki/synthesis/  → cross-topic connections
               ↓
🔗 Everything linked with [[wikilinks]]
               ↓
🌐 Obsidian graph view renders your knowledge map
               ↓
💬 /second-brain-query answers questions with citations
```

**No cloud costs for daily processing. No manual effort. If your Mac was asleep — it catches up the moment you open it.**

---

## ✅ Real Results From Our First Session

When we built this system and ran it for the first time on a real vault, here's exactly what happened:

### Phase 1 — Vault Migration
- Identified **11 old clips** stuck in a wrong Obsidian vault (`knowledge-base/Clippings/`)
- Moved all 11 clips into the correct `~/SecondBrain/raw/` folder
- Merged existing wiki content from the old vault into the new structure

### Phase 2 — First Ingest (`/second-brain-ingest`)
- Ran ingest on **16 raw files** in one pass
- Created **45 wiki entries** across entities, concepts, and sources
- Files processed included:
  - Ruben Hassid LinkedIn growth guides (3 articles)
  - Autonomous AI Agent Team architecture
  - Hermes Agent + OpenClaw multi-agent profiles
  - Claude Code + HeyGen content pipeline
  - Nano Banana Pro image generation guide
  - 36 bookmarked tweets (April 2026)
  - AI wrapper app case studies
  - Vibe Coding guide with Blink.new
  - Veo video prompt guide
  - Token optimization habits
  - And more

### Phase 3 — Query Test (`/second-brain-query`)
- Asked: *"What is the strategy to grow on LinkedIn?"*
- Got a fully cited answer synthesizing Ruben Hassid's 5-layer strategy with source links
- Result saved to `outputs/2026-04-17 LinkedIn Growth Strategy.md`

### Phase 4 — Lint Health Check (`/second-brain-lint`)
- Found **15 broken wikilinks** in the freshly built wiki
- Identified **7 naming mismatches** (e.g. `[[Claude Code]]` pointing to `claude-code.md`)
- Identified **8 truly missing entries** (Multi-Agent Systems, Ollama, Gemini, etc.)
- Fixed all issues:
  - Created 5 new concept entries: `Multi-Agent Systems`, `Ollama`, `Gemini`, `Remotion`, `MCP`
  - Fixed all 4 `[[AI Content Creation]]` → `[[Content Creation Automation]]` redirects
  - Added `[[Anthropic]]` links to `claude-code` and `ai-agents` entries
  - Expanded the only stub (`open-montage.md`, 66 words) to full entry
  - Result: **15 broken links → 1** (one intentionally deferred)

### Phase 5 — Auto-Ingest Setup
- Wrote `auto_ingest.py` — Python script using Ollama REST API (no external dependencies)
- Debugged IPv6 vs IPv4 issue (`localhost` → `127.0.0.1`)
- Fixed qwen3 thinking model issue (reads `thinking` field when `response` is empty)
- Settled on `gemma3:4b` as most reliable model for structured output
- Set up macOS `launchd` plist to run at **4:07am every 2 days** automatically

### Final State
```
Total wiki entries:     45
Broken wikilinks:        1 (intentionally deferred)
Stubs:                   0
Auto-ingest:       Active (4:07am, every 2 days, free local AI)
```

---

## 🆚 What Makes This Different

This repo extends [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain) with a fully automated, zero-cost local pipeline:

| Feature | Original | This Repo |
|---|:---:|:---:|
| Claude Code slash commands | ✅ | ✅ |
| Obsidian vault structure | ✅ | ✅ |
| Setup wizard `/second-brain` | ✅ | ✅ |
| **Free local AI auto-ingest (Ollama)** | ❌ | ✅ |
| **macOS launchd scheduler (every 2 days, 4am)** | ❌ | ✅ |
| **Catches up if Mac was asleep** | ❌ | ✅ |
| **Dry-run mode (preview before writing)** | ❌ | ✅ |
| **Lint with specific broken link fixes** | ❌ | ✅ |
| **`wiki/synthesis/` tier** | ❌ | ✅ |
| **qwen3 thinking model compatibility** | ❌ | ✅ |

---

## 💡 Use Cases

- **AI researcher** — clip papers, threads, and tool announcements. Query: *"What have I saved about multi-agent systems?"*
- **Content creator** — save viral posts and hooks. Query: *"What LinkedIn hooks have I collected?"*
- **Developer** — clip tutorials, docs, Stack Overflow threads. Query: *"How do I set up Ollama with Docker?"*
- **Student** — save lecture notes and reading summaries. Graph view shows how concepts connect.
- **Entrepreneur** — clip business ideas and case studies. Query: *"What SaaS strategies have I researched?"*
- **Investor** — track market trends and news. Query: *"What have I saved about AI infrastructure?"*
- **Job seeker** — clip job advice, resume tips, company research. Build a knowledge map before interviews.
- **Writer** — save inspiration, quotes, and research. Query: *"What do I know about persuasive writing?"*
- **Anyone who reads a lot** — stop losing things you've read. Everything becomes connected and searchable.

---

## 📦 Prerequisites

| Tool | What it is | Install |
|---|---|---|
| **Obsidian** | Markdown editor with graph view | [obsidian.md](https://obsidian.md) |
| **Ollama** | Runs AI models locally on your Mac, free | [ollama.com](https://ollama.com) |
| **Claude Code** | AI coding assistant with slash commands | [claude.ai/code](https://claude.ai/code) |
| **Obsidian Web Clipper** | Chrome/Firefox extension to save articles | [obsidian.md/clipper](https://obsidian.md/clipper) |

> **macOS required** for the auto-scheduler (launchd). Linux: use `cron`. Windows: see [Roadmap](#-roadmap).

---

## 🚀 Full Setup — Step by Step

Estimated time: **15 minutes**

---

### Step 1 — Clone This Repo

```bash
git clone https://github.com/nitesht2/second-brain-ai
cd second-brain-ai
```

---

### Step 2 — Create Your Vault

```bash
mkdir -p ~/SecondBrain/{raw/processed,wiki/{entities,concepts,sources,synthesis},outputs}
cp vault-template/CLAUDE.md ~/SecondBrain/
cp vault-template/wiki/index.md ~/SecondBrain/wiki/
cp vault-template/wiki/log.md ~/SecondBrain/wiki/
```

This creates:
```
~/SecondBrain/
├── raw/              ← clips land here automatically
│   └── processed/    ← moved here after processing
├── wiki/
│   ├── entities/     ← people, companies, tools
│   ├── concepts/     ← ideas, frameworks, strategies
│   ├── sources/      ← summaries of each clip
│   ├── synthesis/    ← cross-topic insights
│   ├── index.md      ← master index
│   └── log.md        ← change log
├── outputs/          ← query results and lint reports
└── CLAUDE.md         ← vault instructions for Claude
```

---

### Step 3 — Open in Obsidian

1. Open **Obsidian**
2. Click **"Open folder as vault"**
3. Select `~/SecondBrain`
4. Click the **graph icon** in the left sidebar → Graph View

> The graph starts empty. Every time ingest runs, new nodes appear automatically.

---

### Step 4 — Configure Web Clipper

1. Install [Obsidian Web Clipper](https://obsidian.md/clipper) in Chrome
2. Click the extension icon → **Settings**
3. Set **Note location** to `raw`
4. Name the template (e.g. "Brain Dump")
5. Test: clip any webpage → check `~/SecondBrain/raw/` for the file

---

### Step 5 — Install Ollama and Pull a Model

```bash
# After installing Ollama from https://ollama.com:
ollama pull gemma3:4b        # recommended — fast, reliable, ~3GB

# Optional: better quality, requires more RAM
ollama pull qwen3.5:9b       # ~7GB, better at complex connections
```

Verify:
```bash
ollama list    # should show gemma3:4b
```

---

### Step 6 — Install Slash Commands

```bash
cp claude-commands/*.md ~/.claude/commands/
```

In Claude Code you now have:

| Command | What it does |
|---|---|
| `/second-brain` | Setup wizard — checks your full configuration |
| `/second-brain-ingest` | Processes raw clips with Claude Sonnet |
| `/second-brain-query [question]` | Answers questions from your wiki with citations |
| `/second-brain-lint` | Finds broken links, orphans, stubs, gaps |

---

### Step 7 — Set Up Auto-Ingest

```bash
# Copy script to vault
cp auto_ingest.py ~/SecondBrain/

# Test with dry run (no files written)
python3 ~/SecondBrain/auto_ingest.py --dry-run

# Install scheduler (runs every 2 days at 4:07am automatically)
cp launchd/com.nitesh.secondbrain-ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist

# Verify (should show: -  0  com.nitesh.secondbrain-ingest)
launchctl list | grep secondbrain
```

> **Mac was closed at 4:07am?** No problem — the script runs the moment you open your Mac. Built into macOS launchd by default.

---

### Step 8 — Run the Setup Wizard

In Claude Code:
```
/second-brain
```

This checks your full configuration and tells you what's missing.

---

### Step 9 — Test the Full Pipeline

```bash
# Drop a test clip
echo "# Gemma 3 by Google
Gemma 3 is an open-source model family by Google. Runs locally via Ollama." \
> ~/SecondBrain/raw/test-gemma.md

# Process it now (free, local)
python3 ~/SecondBrain/auto_ingest.py

# Check results
ls ~/SecondBrain/wiki/sources/
ls ~/SecondBrain/wiki/entities/
```

Open Obsidian — new nodes appear in the graph view.

---

## 💬 Querying Your Wiki

In Claude Code, ask anything:

```
/second-brain-query What is the best strategy to grow on LinkedIn?
/second-brain-query What tools have I saved for AI video generation?
/second-brain-query Who are the people I've been following in AI?
/second-brain-query What frameworks have I learned about for multi-agent systems?
```

Claude searches your wiki, synthesizes an answer with `[[wikilinks]]` citations, and saves the result to `outputs/`.

---

## 🔍 Running a Lint Check

```
/second-brain-lint
```

Example output:
```
## Summary
- Total wiki entries: 45
- Orphaned notes (< 2 links): 0
- Broken wikilinks: 15 → fixed to 1
- Stubs to expand: 1

## Errors (must fix)
- [ ] [[Multi-Agent Systems]] — referenced 10x, no wiki entry exists

## Suggestions
- Connect [[claude-code]] to [[Anthropic]] — claude-code never links to its creator
- Connect [[open-montage]] to [[Content Creation Automation]] — strong overlap
```

---

## ⚙️ Configuration

Edit the top of `auto_ingest.py`:

```python
MODEL      = "gemma3:4b"   # or "qwen3.5:9b" for higher quality
MIN_HOURS  = 48            # hours between runs — 48 = every 2 days, 24 = daily
MAX_TOKENS = 3000          # max tokens per model call
RAW_CHUNK  = 3500          # characters from each clip sent to the model
```

To change the run time (e.g. 6am instead of 4am):
```bash
# Edit the plist
nano ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
# Change Hour from 4 to your preferred hour

# Reload
launchctl unload ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
```

---

## 🔄 Two-Speed Pipeline

| | 🤖 Automatic (Local AI) | ✨ Manual (Claude Sonnet) |
|---|---|---|
| **Trigger** | Every 2 days at 4am, automatically | You type `/second-brain-ingest` |
| **Cost** | Free — Ollama + Gemma 3 | Claude Code tokens |
| **Quality** | Good — correct structure + basic links | Excellent — deep connections, nuanced tagging |
| **Speed** | ~30-60s per clip | ~10-20s per clip |
| **Best for** | Daily clips, tweets, article bookmarks | Key research, important content |

---

## 📁 Repo Structure

```
second-brain-ai/
├── README.md                                        ← you are here
├── auto_ingest.py                                   ← local AI ingest script
├── CONTRIBUTING.md
├── LICENSE
├── .gitignore
│
├── claude-commands/                                 ← copy to ~/.claude/commands/
│   ├── second-brain.md                              ← /second-brain (setup wizard)
│   ├── second-brain-ingest.md                       ← /second-brain-ingest
│   ├── second-brain-query.md                        ← /second-brain-query
│   └── second-brain-lint.md                         ← /second-brain-lint
│
├── launchd/                                         ← macOS auto-scheduler
│   └── com.nitesh.secondbrain-ingest.plist          ← every 2 days at 4:07am
│
└── vault-template/                                  ← copy into ~/SecondBrain/
    ├── CLAUDE.md                                    ← vault rules for Claude
    ├── wiki/
    │   ├── index.md                                 ← master index template
    │   ├── log.md                                   ← change log template
    │   ├── entities/
    │   ├── concepts/
    │   ├── sources/
    │   └── synthesis/
    ├── raw/
    │   └── processed/
    └── outputs/
```

---

## 🐛 Troubleshooting

**"Ollama not reachable"**
Open the Ollama app (check your menu bar). Or run `ollama serve` in Terminal.

**launchd job not firing**
```bash
launchctl list | grep secondbrain                   # check it loaded
cat ~/SecondBrain/outputs/ingest-daemon.log         # read the error
```

**Web Clipper saving to wrong folder**
Extension settings → set **Note location** to `raw` (not `Clippings`).

**qwen3.5 returns empty response field**
Expected behavior — qwen3 is a thinking model and puts output in the `thinking` field. This script handles it automatically. No action needed. Use `gemma3:4b` for simpler behavior.

**Wiki entries have underscores in filenames**
Local 4B models sometimes output underscores instead of spaces. Rename in Obsidian, or use `/second-brain-ingest` with Claude for cleaner filenames.

**Mac was off (not sleeping) at schedule time**
launchd only catches up from sleep — a full shutdown will miss the run. It will fire again at the next scheduled time (2 days later). For daily peace of mind, set `MIN_HOURS = 24` in `auto_ingest.py`.

---

## 🗺️ Roadmap

- [ ] Windows Task Scheduler support (alternative to launchd)
- [ ] Linux cron setup guide
- [ ] Auto-update `wiki/index.md` after every ingest run
- [ ] `wiki/synthesis/` auto-generation (cross-topic summaries)
- [ ] PDF and YouTube transcript ingestion
- [ ] Slack/Discord notification when ingest completes
- [ ] Web dashboard to browse vault without Obsidian

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Windows/Linux support, better local model prompts, and new ingest sources are especially welcome.

---

## 🙏 Credits

Built by [@NiteshTechAI](https://x.com/NiteshTechAI)

Standing on the shoulders of:
- [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain) — original system and slash commands
- [swyx/brain](https://github.com/swyxio/brain) — public Obsidian vault inspiration
- [Andrej Karpathy](https://x.com/karpathy) — LLM-Wiki pattern
- [Ruben Hassid](https://ruben.substack.com) — AI productivity and content workflows

---

## 📄 License

MIT — free to use, modify, and share.

If you build something with this, tag [@NiteshTechAI](https://x.com/NiteshTechAI) on X. 🚀
