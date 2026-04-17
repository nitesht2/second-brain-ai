# 🧠 Second Brain AI

> **Clip anything. Forget about it. Wake up to a connected knowledge graph.**

An automated personal knowledge base built on **Obsidian + Claude Code + local LLMs**. The LLM is the librarian. You're the curator.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/Runs%20on-Ollama-black)](https://ollama.com)
[![Claude Code](https://img.shields.io/badge/Claude-Code-orange)](https://claude.ai/code)
[![Obsidian](https://img.shields.io/badge/Works%20with-Obsidian-7c3aed)](https://obsidian.md)

---

## ✨ How It Works

```
📎 You clip an article           →   lands in raw/
⏰ Every 2 days at 4am          →   local AI processes it (free)
🗂️  Wiki entries created         →   entities, concepts, sources
🔗 Wikilinks connect everything →   Obsidian graph view lights up
🔍 Ask any question             →   /second-brain-query answers with citations
```

**Zero cost. Zero effort. Runs while you sleep.**

---

## 🆚 This Repo vs. Nicholas Spisak's Original

This is a fork and extension of [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain). Here's what we added:

| Feature | Original | This Repo |
|---|:---:|:---:|
| Claude Code slash commands | ✅ | ✅ |
| Obsidian vault structure | ✅ | ✅ |
| Setup wizard `/second-brain` | ✅ | ✅ |
| **Free local LLM auto-ingest** | ❌ | ✅ |
| **macOS launchd scheduler** | ❌ | ✅ |
| **Runs every 2 days at 4am automatically** | ❌ | ✅ |
| **Dry-run mode for safe testing** | ❌ | ✅ |
| **Detailed lint with auto-fix suggestions** | ❌ | ✅ |
| **`wiki/synthesis/` tier** | ❌ | ✅ |

---

## 📁 Vault Structure

```
~/SecondBrain/
├── raw/                    ← 📥 Drop clips here (Web Clipper saves here)
│   └── processed/          ← ✅ Moved here after ingest
├── wiki/
│   ├── entities/           ← 👤 People, companies, tools
│   ├── concepts/           ← 💡 Ideas, frameworks, strategies
│   ├── sources/            ← 📄 One summary per raw clip
│   ├── synthesis/          ← 🔬 Cross-topic insights
│   ├── index.md            ← 📋 Master index (auto-updated)
│   └── log.md              ← 📝 Change log
├── outputs/                ← 💬 Query results, lint reports
└── CLAUDE.md               ← 🤖 Vault instructions for Claude
```

---

## ⚡ Quick Start

### 1. Clone and set up vault

```bash
git clone https://github.com/nitesht2/second-brain-ai
cd second-brain-ai

# Create your vault
mkdir -p ~/SecondBrain/{raw/processed,wiki/{entities,concepts,sources,synthesis},outputs}
cp vault-template/CLAUDE.md ~/SecondBrain/
cp vault-template/wiki/index.md ~/SecondBrain/wiki/
cp vault-template/wiki/log.md ~/SecondBrain/wiki/
```

### 2. Open in Obsidian

Open Obsidian → **Open folder as vault** → select `~/SecondBrain`

Enable **Graph view** (left sidebar icon) to see connections appear as you ingest.

### 3. Install Claude Code commands

```bash
cp claude-commands/*.md ~/.claude/commands/
```

### 4. Install Ollama (free local AI)

```bash
# Install from https://ollama.com then:
ollama pull gemma3:4b
```

### 5. Set up auto-ingest

```bash
cp auto_ingest.py ~/SecondBrain/
cp launchd/com.nitesh.secondbrain-ingest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
```

### 6. Set up Web Clipper

Install [Obsidian Web Clipper](https://obsidian.md/clipper) in Chrome.
Set **Note location** → `raw`. That's it — clip anything and it lands automatically.

### 7. Run the setup wizard

In Claude Code:
```
/second-brain
```

---

## 🛠️ Claude Code Commands

| Command | What It Does |
|---|---|
| `/second-brain` | Guided setup wizard for new vaults |
| `/second-brain-ingest` | Process all raw clips with Claude Sonnet (best quality) |
| `/second-brain-query [question]` | Search your wiki, get a cited answer |
| `/second-brain-lint` | Health check: broken links, orphans, stubs, gaps |

### Example queries

```
/second-brain-query What is the best strategy to grow on LinkedIn?
/second-brain-query Who are the top AI creators I've been following?
/second-brain-query What tools have I saved for video automation?
```

---

## 🤖 Auto-Ingest (Free, Local, Zero Tokens)

The `auto_ingest.py` script runs every 2 days at 4:07am using your local Ollama model — no Claude tokens, no internet, no cost.

```bash
# Test it (no writes)
python3 ~/SecondBrain/auto_ingest.py --dry-run

# Run manually
python3 ~/SecondBrain/auto_ingest.py
```

**If your Mac was asleep at 4:07am** — it runs the moment you open your Mac. Nothing missed.

### Configuration

Edit the top of `auto_ingest.py`:

```python
MODEL     = "gemma3:4b"   # or qwen3.5:9b for higher quality
MIN_HOURS = 48            # hours between runs (48 = every 2 days)
```

---

## 🔄 Two-Speed Pipeline

| | Auto (Local LLM) | Manual (Claude Sonnet) |
|---|---|---|
| **Trigger** | Every 2 days at 4am | `/second-brain-ingest` |
| **Cost** | Free | Claude Code tokens |
| **Quality** | Good (structure + basic links) | Excellent (deep connections) |
| **Best for** | Daily clips, tweets, articles | Key research, important content |

**Recommended:** Let local LLM handle the daily drip. Use Claude for anything that matters.

---

## 🔍 Lint Health Check

Run `/second-brain-lint` to audit your wiki:

```
## Summary
- Total wiki entries: 45
- Orphaned notes (< 2 links): 0
- Broken wikilinks: 3
- Stubs to expand: 1

## Errors (must fix)
- [ ] [[Multi-Agent Systems]] — referenced 10x but no entry exists

## Suggestions
- Connect [[Ruben Hassid]] to [[Token Optimization]] — strong overlap
```

---

## 📋 Prerequisites

- **macOS** — launchd scheduler is macOS-only (Linux users can use cron)
- **[Obsidian](https://obsidian.md)** — free Markdown editor with graph view
- **[Ollama](https://ollama.com)** — free local LLM runtime
- **[Claude Code](https://claude.ai/code)** — for slash commands
- **[Obsidian Web Clipper](https://obsidian.md/clipper)** — Chrome/Firefox extension

---

## 🐛 Troubleshooting

**"Ollama not reachable"**
Open the Ollama app first. Check it's running in your menu bar.

**launchd job not firing**
```bash
launchctl list | grep secondbrain          # check loaded
cat ~/SecondBrain/outputs/ingest-daemon.log  # check errors
```

**Model returns empty response (qwen3.5)**
This is expected — qwen3 is a thinking model. The script auto-reads the `thinking` field. No action needed.

**Web Clipper saving to wrong folder**
Open the extension → Settings → set Note location to `raw` (not `Clippings`).

---

## 🗺️ Roadmap

- [ ] Windows support (Task Scheduler alternative to launchd)
- [ ] `wiki/synthesis/` auto-generation (cross-topic insight summaries)
- [ ] Automatic `wiki/index.md` updates after each ingest
- [ ] Support for PDF and YouTube transcript ingestion
- [ ] Discord/Slack notification when ingest completes

---

## 🙏 Credits

Built by [@NiteshTechAI](https://x.com/NiteshTechAI)

Standing on the shoulders of:
- [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain) — original system and slash commands
- [swyx/brain](https://github.com/swyxio/brain) — public Obsidian vault inspiration
- [Andrej Karpathy](https://x.com/karpathy) — LLM-Wiki pattern
- [Ruben Hassid](https://ruben.substack.com) — AI productivity workflows

---

## 📄 License

MIT — free to use, modify, and share.

If you build something cool, tag [@NiteshTechAI](https://x.com/NiteshTechAI) on X. 🚀
