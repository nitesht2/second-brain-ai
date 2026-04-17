<div align="center">

# 🧠 Second Brain AI

### Clip anything. Wake up to a connected knowledge graph.

**An automated personal knowledge base built on Obsidian + Claude Code + free local AI.**
**You save articles. The AI organizes them into a searchable wiki while you sleep.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Runs%20on-Ollama-black)](https://ollama.com)
[![Claude Code](https://img.shields.io/badge/Works%20with-Claude%20Code-orange)](https://claude.ai/code)
[![Obsidian](https://img.shields.io/badge/Visualized%20in-Obsidian-7c3aed)](https://obsidian.md)
[![macOS](https://img.shields.io/badge/Platform-macOS-lightgrey)](#)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[🚀 Quick Start](#-quick-start-30-seconds) • [📖 Full Setup](#-full-setup-detailed) • [💡 Use Cases](#-who-its-for) • [🐛 Troubleshooting](#-troubleshooting)

---

![Obsidian Graph View](docs/screenshots/graph-view.png)

*Your knowledge graph after a single ingest session — 45 wiki entries, all auto-connected.*

</div>

---

## 📋 Table of Contents

- [What It Does](#-what-it-does)
- [Who It's For](#-who-its-for)
- [Quick Start](#-quick-start-30-seconds)
- [Prerequisites](#-prerequisites)
- [Full Setup](#-full-setup-detailed)
- [Usage](#-usage)
- [Configuration](#️-configuration)
- [Two-Speed Pipeline](#-two-speed-pipeline)
- [Proven Results](#-proven-results)
- [Repo Structure](#-repo-structure)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#️-roadmap)
- [Contributing](#-contributing)
- [Credits](#-credits)

---

## 🎯 What It Does

```
📎 Clip article with Obsidian Web Clipper
               ↓
📁 Lands in ~/SecondBrain/raw/
               ↓
⏰ Every 2 days at 4am  (automatic, macOS launchd)
               ↓
🤖 Local AI processes each clip  (Ollama + Gemma 3, completely free)
               ↓
🗂️  Wiki entries auto-created:
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

**Zero cost for daily processing. Zero manual effort. If your Mac was asleep — it catches up automatically.**

---

## 👥 Who It's For

This tool is for anyone who reads a lot online and wants their notes to actually connect. Use cases:

- 🔬 **AI researchers** — clip papers and threads. Query: *"What have I saved about multi-agent systems?"*
- ✍️ **Content creators** — save viral posts and hooks. Query: *"What LinkedIn hooks have I collected?"*
- 💻 **Developers** — clip tutorials, docs, Stack Overflow. Query: *"How did I set up Ollama last time?"*
- 🎓 **Students** — save lecture notes and readings. Graph view shows how concepts link.
- 💼 **Entrepreneurs** — clip business case studies. Query: *"What SaaS strategies have I researched?"*
- 📈 **Investors** — track trends and news. Query: *"What have I saved about AI infrastructure?"*
- 🎯 **Job seekers** — clip advice, tips, company research. Build a map before interviews.
- 📝 **Writers** — save inspiration, quotes, research. Query: *"What do I know about persuasion?"*
- 🧠 **Anyone who reads a lot** — stop losing what you've read. Everything becomes searchable.

---

## ⚡ Quick Start (30 seconds)

**Requires:** macOS, [Obsidian](https://obsidian.md), [Ollama](https://ollama.com), [Claude Code](https://claude.ai/code)

```bash
git clone https://github.com/nitesht2/second-brain-ai
cd second-brain-ai
./setup.sh
ollama pull gemma3:4b
```

Then in Claude Code:
```
/second-brain
```

That's it. Install the [Web Clipper](https://obsidian.md/clipper), point it at the `raw` folder, and start clipping. The auto-ingest runs every 2 days at 4:07am automatically.

> 👉 **For the full guided walkthrough, see [Full Setup](#-full-setup-detailed) below.**

---

## 📦 Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| **Obsidian** | Markdown editor with graph view | [obsidian.md](https://obsidian.md) |
| **Ollama** | Local AI runtime (free) | [ollama.com](https://ollama.com) |
| **Claude Code** | Slash commands | [claude.ai/code](https://claude.ai/code) |
| **Web Clipper** | Chrome/Firefox extension | [obsidian.md/clipper](https://obsidian.md/clipper) |

> **macOS required** for the auto-scheduler. Linux: use cron. Windows: see [Roadmap](#️-roadmap).

---

## 🚀 Full Setup (Detailed)

<details>
<summary><b>📘 Click to expand the full 9-step walkthrough (~15 min)</b></summary>

### Step 1 — Clone the repo

```bash
git clone https://github.com/nitesht2/second-brain-ai
cd second-brain-ai
```

### Step 2 — Create your vault

```bash
mkdir -p ~/SecondBrain/{raw/processed,wiki/{entities,concepts,sources,synthesis},outputs}
cp vault-template/CLAUDE.md ~/SecondBrain/
cp vault-template/wiki/index.md ~/SecondBrain/wiki/
cp vault-template/wiki/log.md ~/SecondBrain/wiki/
```

Structure created:
```
~/SecondBrain/
├── raw/              ← clips land here
│   └── processed/    ← moved after processing
├── wiki/
│   ├── entities/     ← people, companies, tools
│   ├── concepts/     ← ideas, frameworks
│   ├── sources/      ← clip summaries
│   ├── synthesis/    ← cross-topic insights
│   ├── index.md      ← master index
│   └── log.md        ← change log
├── outputs/          ← query/lint results
└── CLAUDE.md         ← vault rules for Claude
```

### Step 3 — Open in Obsidian

1. Open **Obsidian**
2. Click **"Open folder as vault"** → select `~/SecondBrain`
3. Click the **graph icon** in the sidebar → Graph View

### Step 4 — Configure Web Clipper

1. Install [Obsidian Web Clipper](https://obsidian.md/clipper) in Chrome
2. Extension settings → set **Note location** to `raw`
3. Name the template (e.g. "Brain Dump")
4. Test: clip any webpage → check `~/SecondBrain/raw/`

### Step 5 — Install Ollama + pull a model

```bash
ollama pull gemma3:4b        # recommended, ~3GB
ollama pull qwen3.5:9b       # optional, higher quality, ~7GB
```

### Step 6 — Install slash commands

```bash
cp claude-commands/*.md ~/.claude/commands/
```

### Step 7 — Set up auto-ingest

```bash
cp auto_ingest.py ~/SecondBrain/
python3 ~/SecondBrain/auto_ingest.py --dry-run
cp launchd/com.nitesh.secondbrain-ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
launchctl list | grep secondbrain
```

Expected: `-  0  com.nitesh.secondbrain-ingest`

### Step 8 — Run the setup wizard

In Claude Code:
```
/second-brain
```

### Step 9 — Test the full pipeline

```bash
echo "# Gemma 3 by Google
Runs locally via Ollama for free." > ~/SecondBrain/raw/test-gemma.md

python3 ~/SecondBrain/auto_ingest.py
```

Open Obsidian — new nodes appear in the graph.

</details>

---

## 💬 Usage

Four slash commands in Claude Code:

| Command | What it does | Uses tokens? |
|---|---|:---:|
| `/second-brain` | Setup wizard — checks your configuration | No |
| `/second-brain-ingest` | Process raw clips with Claude Sonnet (best quality) | Yes |
| `/second-brain-query [question]` | Ask questions, get cited answers from your wiki | Yes |
| `/second-brain-lint` | Health check: broken links, orphans, stubs, gaps | Yes |

**Plus the free local script:**

```bash
python3 ~/SecondBrain/auto_ingest.py           # run manually
python3 ~/SecondBrain/auto_ingest.py --dry-run # preview only
```

The local script runs automatically every 2 days — you rarely need to run it by hand.

---

## ⚙️ Configuration

Edit the top of `auto_ingest.py`:

```python
MODEL      = "gemma3:4b"   # or "qwen3.5:9b" for higher quality
MIN_HOURS  = 48            # 48 = every 2 days, 24 = daily
MAX_TOKENS = 3000          # max tokens per model call
RAW_CHUNK  = 3500          # chars per clip sent to model
```

<details>
<summary><b>Change the run time</b></summary>

```bash
nano ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
# Change <integer>4</integer> (Hour) to your preferred hour

launchctl unload ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
```

</details>

---

## 🔄 Two-Speed Pipeline

| | 🤖 Auto (Local AI) | ✨ Manual (Claude Sonnet) |
|---|---|---|
| **Trigger** | Every 2 days at 4am | You type `/second-brain-ingest` |
| **Cost** | Free | Claude Code tokens |
| **Quality** | Good | Excellent |
| **Speed** | ~30-60s per clip | ~10-20s per clip |
| **Best for** | Daily clips, bookmarks | Key research, deep articles |

**Recommended:** Let local AI handle the daily drip. Run Claude for anything that truly matters.

---

## 🔥 Proven Results

> First real run on a personal vault: **16 files ingested → 45 wiki entries created → 15 broken links detected → 14 auto-fixed in 5 minutes.**
>
> Zero tokens spent on the daily pipeline. Everything searchable in Obsidian graph view.

<details>
<summary><b>Full session breakdown</b></summary>

- **Phase 1:** Migrated 11 old clips from a wrong vault into the correct structure
- **Phase 2:** Ran `/second-brain-ingest` on 16 files → 45 wiki entries created
- **Phase 3:** Asked `/second-brain-query "LinkedIn growth strategy"` → cited answer saved to outputs/
- **Phase 4:** Ran `/second-brain-lint` → found 15 broken links, 1 stub → fixed to 1 broken (intentionally deferred)
- **Phase 5:** Built `auto_ingest.py` + macOS launchd plist for fully automated, free, local daily processing

</details>

---

## 📁 Repo Structure

<details>
<summary><b>Expand file tree</b></summary>

```
second-brain-ai/
├── README.md                                     ← you are here
├── setup.sh                                      ← one-command install
├── auto_ingest.py                                ← local AI ingest script
├── CONTRIBUTING.md
├── LICENSE
├── .gitignore
│
├── claude-commands/                              ← copy to ~/.claude/commands/
│   ├── second-brain.md                           ← /second-brain (setup wizard)
│   ├── second-brain-ingest.md                    ← /second-brain-ingest
│   ├── second-brain-query.md                     ← /second-brain-query
│   └── second-brain-lint.md                      ← /second-brain-lint
│
├── launchd/                                      ← macOS scheduler
│   └── com.nitesh.secondbrain-ingest.plist
│
├── docs/
│   └── screenshots/
│       └── graph-view.png                        ← the hero image
│
└── vault-template/                               ← copy into ~/SecondBrain/
    ├── CLAUDE.md
    ├── wiki/
    │   ├── index.md
    │   ├── log.md
    │   ├── entities/
    │   ├── concepts/
    │   ├── sources/
    │   └── synthesis/
    ├── raw/
    │   └── processed/
    └── outputs/
```

</details>

---

## 🐛 Troubleshooting

<details>
<summary><b>"Ollama not reachable"</b></summary>

Open the Ollama app (check menu bar) or run `ollama serve` in terminal.
</details>

<details>
<summary><b>launchd job not firing</b></summary>

```bash
launchctl list | grep secondbrain                 # check loaded
cat ~/SecondBrain/outputs/ingest-daemon.log       # read errors
```
</details>

<details>
<summary><b>Web Clipper saving to wrong folder</b></summary>

Extension settings → set **Note location** to `raw` (not `Clippings`).
</details>

<details>
<summary><b>qwen3.5 returns empty response field</b></summary>

Expected — qwen3 is a thinking model. The script auto-reads the `thinking` field. No action needed.
</details>

<details>
<summary><b>Wiki entries have underscores in filenames</b></summary>

Local 4B models sometimes use underscores. Rename in Obsidian or use `/second-brain-ingest` with Claude.
</details>

<details>
<summary><b>Mac was fully shut down (not sleeping)</b></summary>

launchd only catches up from sleep. A full shutdown misses the run. It fires again at the next scheduled time.
</details>

---

## 🗺️ Roadmap

- [ ] Windows support (Task Scheduler)
- [ ] Linux cron setup guide
- [ ] Auto-update `wiki/index.md` after every ingest
- [ ] `wiki/synthesis/` auto-generation
- [ ] PDF + YouTube transcript ingestion
- [ ] Discord/Slack notification on ingest completion
- [ ] Web dashboard to browse vault without Obsidian

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Windows/Linux support, better local model prompts, and new ingest sources especially appreciated.

---

## 🙏 Credits

Built by [@NiteshTechAI](https://x.com/NiteshTechAI)

Standing on the shoulders of:
- [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain) — original system
- [swyx/brain](https://github.com/swyxio/brain) — public vault inspiration
- [Andrej Karpathy](https://x.com/karpathy) — LLM-Wiki pattern
- [Ruben Hassid](https://ruben.substack.com) — AI productivity workflows

---

## 📄 License

MIT — free to use, modify, and share.

If you build something cool, tag [@NiteshTechAI](https://x.com/NiteshTechAI) on X. 🚀

---

<div align="center">

**⭐ Star this repo** if it helps you organize your knowledge.

</div>
