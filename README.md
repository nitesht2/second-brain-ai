<div align="center">

# 🧠 Second Brain AI

### Clip anything. Wake up to a connected knowledge graph.

**Local AI that organizes everything you read and watch into a searchable Obsidian wiki — automatically, for free.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/Platform-macOS-lightgrey)](#)
[![Ollama](https://img.shields.io/badge/Runs%20on-Ollama-black)](https://ollama.com)
[![Claude Code](https://img.shields.io/badge/Works%20with-Claude%20Code-orange)](https://claude.ai/code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Quick Start](#-quick-start) • [How It Works](#-how-it-works) • [Usage](#-usage) • [Setup Guide](#-full-setup) • [Troubleshooting](#-troubleshooting)

---

</div>

---

## Why This Exists

Most knowledge tools are write-heavy. You read 20 articles a week, bookmark them, and never look at them again.

This flips it: **clip once, AI organizes overnight.** Everything you read and watch turns into a searchable, linked wiki while you sleep. No manual filing. No tagging. No API keys. Runs entirely on your Mac for free.

> *"The LLM is the librarian, you're the curator."* — inspired by [Andrej Karpathy](https://x.com/karpathy)

---

## How It Works

```
📎 Clip article or YouTube video  (Obsidian Web Clipper or bookmarklet)
               ↓
📁 Lands in ~/SecondBrain/raw/
               ↓
⏰ Every 2 days at 4am  (macOS launchd, fully automatic)
               ↓
🤖 Ingest  —  Ollama + Gemma 3, completely free
    wiki/entities/   → people, companies, tools
    wiki/concepts/   → ideas, frameworks, strategies
    wiki/sources/    → one summary per clip
               ↓ auto
🧩 Synthesis  —  cross-topic patterns, contradictions, key insights
    wiki/synthesis/  → generated automatically after every ingest
               ↓ auto
📋 wiki/index.md  —  master table of contents, always up to date
               ↓
🌐 Obsidian graph view  —  your knowledge map, fully linked
               ↓
💬 /second-brain-query  —  ask questions, get cited answers
```

**Zero cost. Zero manual effort. One clip = one wiki entry with [[wikilinks]] to everything related.**

---

## What You Can Clip

| Format | How to capture | What happens |
|---|---|---|
| **YouTube video** | Obsidian Web Clipper or → Brain bookmarklet | Full transcript fetched automatically |
| **Article / blog** | Obsidian Web Clipper | Full page content processed |
| **PDF** | Drop into `raw/` folder | Text extracted via pdftotext, fallback to pypdf |
| **Plain text / notes** | Drop `.txt` into `raw/` | Read as-is |

**Cross-device:** Obsidian Web Clipper works on any device (phone, work computer). Files sync to your Mac via Obsidian Sync — ingest picks them up automatically.

**Duplicate protection:** clip the same YouTube video twice and the second one is silently skipped.

---

## ⚡ Quick Start

**Requires:** macOS 12+, 16GB+ RAM, [Obsidian](https://obsidian.md), [Ollama](https://ollama.com), [Claude Code](https://claude.ai/code)

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

That's it. Install [Obsidian Web Clipper](https://obsidian.md/clipper), set the save location to `raw`, and start clipping. Ingest runs automatically every 2 days at 4am.

**For YouTube:** open `http://localhost:7331/setup` in your browser and drag the red **→ Brain** button to your bookmarks bar.

---

## 💬 Usage

Five slash commands in Claude Code:

| Command | What it does |
|---|---|
| `/second-brain` | Setup wizard — checks your configuration |
| `/second-brain-ingest` | Process raw clips now with Claude Sonnet (best quality) |
| `/second-brain-query [question]` | Ask questions, get cited answers from your wiki |
| `/second-brain-lint` | Health check: broken links, orphans, stubs, gaps |
| `/second-brain-synthesis` | Generate cross-topic insight notes on demand |

**Local script (free, no tokens):**

```bash
python3 ~/SecondBrain/auto_ingest.py                        # run ingest now
python3 ~/SecondBrain/auto_ingest.py --dry-run              # preview, no writes
python3 ~/SecondBrain/auto_ingest.py --synthesize           # generate synthesis notes
python3 ~/SecondBrain/auto_ingest.py --synthesize --dry-run # preview synthesis
```

The local script runs automatically every 2 days. Use slash commands when you want higher quality output (Claude Sonnet vs Gemma 3) or want to query your wiki.

---

## 🔄 Two-Speed Pipeline

| | 🤖 Auto (Local AI) | ✨ Manual (Claude Sonnet) |
|---|---|---|
| **Trigger** | Every 2 days at 4am | `/second-brain-ingest` |
| **Cost** | Free | Claude Code tokens |
| **Quality** | Good | Excellent |
| **Speed** | ~30-60s per clip | ~10-20s per clip |

**Recommended:** let local AI handle the daily drip. Run Claude for anything that truly matters.

---

## 📦 Prerequisites

| Tool | Purpose | Download |
|---|---|---|
| **Obsidian** | View your knowledge graph | [obsidian.md](https://obsidian.md) |
| **Ollama** | Run AI models locally, free | [ollama.com](https://ollama.com) |
| **Claude Code** | Powers the slash commands | [claude.ai/code](https://claude.ai/code) |
| **Obsidian Web Clipper** | One-click page saving | [obsidian.md/clipper](https://obsidian.md/clipper) |

> macOS required for the auto-scheduler. Linux: use cron instead of launchd.

---

## 🚀 Full Setup

<details>
<summary><b>Click to expand the full walkthrough (~15 min)</b></summary>

### Step 1 — Clone and run setup

```bash
git clone https://github.com/nitesht2/second-brain-ai
cd second-brain-ai
./setup.sh
```

This creates the vault, copies scripts, installs slash commands, and starts both launchd agents (ingest scheduler + brain server).

### Step 2 — Pull an AI model

```bash
ollama pull gemma3:4b        # recommended — fast, 3GB, great structured output
ollama pull qwen3.5:9b       # optional — better quality, 7GB, needs 16GB+ RAM
```

### Step 3 — Open vault in Obsidian

1. Open Obsidian → **Open folder as vault** → select `~/SecondBrain`
2. Click the graph icon → Graph View

### Step 4 — Configure Web Clipper

1. Install [Obsidian Web Clipper](https://obsidian.md/clipper) in Chrome/Firefox
2. Extension settings → set **Note location** to `raw`
3. Test: clip any webpage → check `~/SecondBrain/raw/`

### Step 5 — Install Python dependencies

```bash
brew install poppler                                              # PDF extraction
pip3 install --break-system-packages youtube-transcript-api pypdf
```

### Step 6 — Set up YouTube bookmarklet (optional)

Open `http://localhost:7331/setup` in Chrome. Drag the red **→ Brain** button to your bookmarks bar. One click on any YouTube page saves it instantly.

### Step 7 — Test the pipeline

```bash
python3 ~/SecondBrain/auto_ingest.py --dry-run
```

Expected output: files detected, wiki entries previewed, no writes. Then run without `--dry-run` to process for real.

### Vault structure created

```
~/SecondBrain/
├── raw/              ← clips land here
│   └── processed/    ← moved here after processing
├── wiki/
│   ├── entities/     ← people, companies, tools
│   ├── concepts/     ← ideas, frameworks, strategies
│   ├── sources/      ← one summary per clip
│   ├── synthesis/    ← cross-topic insights (auto-generated)
│   ├── index.md      ← master table of contents (auto-updated)
│   └── log.md        ← change log
└── outputs/          ← query and lint results
```

</details>

---

## ⚙️ Configuration

Edit the top of `auto_ingest.py`:

| Variable | Default | What it does |
|---|---|---|
| `MODEL` | `"gemma3:4b"` | Switch to `"qwen3.5:9b"` for better quality |
| `MIN_HOURS` | `48` | Hours between auto-runs. Set to `24` for daily. |
| `MAX_TOKENS` | `3000` | Max tokens per model call |
| `RAW_CHUNK` | `3500` | Characters per clip sent to the model |

To change the run time, edit `launchd/com.nitesh.secondbrain-ingest.plist` and reload:

```bash
launchctl unload ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
launchctl load ~/Library/LaunchAgents/com.nitesh.secondbrain-ingest.plist
```

---

## 📁 Repo Structure

```
second-brain-ai/
├── auto_ingest.py              ← local AI ingest (Ollama + Gemma 3)
├── brain_server.py             ← YouTube bookmarklet backend (port 7331)
├── setup.sh                    ← one-command installer
├── claude-commands/            ← /second-brain-* slash commands
├── launchd/                    ← macOS scheduler + brain server agents
└── vault-template/             ← starter vault (copy to ~/SecondBrain)
```

---

## 🐛 Troubleshooting

<details>
<summary><b>Ollama not reachable</b></summary>

Open the Ollama app (check your menu bar) or run `ollama serve` in Terminal.
</details>

<details>
<summary><b>launchd job not firing</b></summary>

```bash
launchctl list | grep secondbrain       # check it's loaded
cat ~/SecondBrain/outputs/ingest-daemon.log   # read errors
```
</details>

<details>
<summary><b>Web Clipper saving to wrong folder</b></summary>

Extension settings → set **Note location** to `raw` (not `Clippings`).
</details>

<details>
<summary><b>YouTube transcript fails</b></summary>

Some videos have no captions or are region-locked. Fallback: copy the transcript from YouTube's "Show transcript" button and save as a `.md` file in `raw/`. Or use yt-dlp:

```bash
brew install yt-dlp
yt-dlp --write-auto-sub --skip-download --sub-lang en URL
```
</details>

<details>
<summary><b>PDF extraction fails</b></summary>

Install the dependencies:

```bash
brew install poppler
pip3 install --break-system-packages pypdf
```

For scanned/image PDFs (no text layer): `brew install tesseract` and convert manually first.
</details>

<details>
<summary><b>Mac was fully shut down (not sleeping)</b></summary>

launchd only catches up from sleep. A full shutdown misses the run. It fires again at the next scheduled time. Run `python3 ~/SecondBrain/auto_ingest.py` manually to process immediately.
</details>

<details>
<summary><b>qwen3.5 returns empty output</b></summary>

Expected — qwen3 is a thinking model. The script auto-reads the `thinking` field. No action needed.
</details>

---

## ✅ What's Built

- [x] Obsidian Web Clipper → auto-ingest (`.md`, `.pdf`, `.txt`, YouTube)
- [x] YouTube transcript detection from Web Clipper frontmatter — works on any device
- [x] Duplicate protection — same video captured twice is silently skipped
- [x] 1-click YouTube bookmarklet — `brain_server.py` runs 24/7 on port 7331
- [x] Local AI via Ollama — zero cost, zero cloud, zero API keys
- [x] `wiki/synthesis/` — cross-topic insights auto-generated after every ingest
- [x] `wiki/index.md` — master table of contents, auto-regenerated
- [x] macOS launchd — ingest every 2 days at 4am, brain server always on
- [x] 5 slash commands for Claude Code
- [x] `setup.sh` — one-command full installer

---

## 🤝 Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

Windows/Linux support, better local model prompts, and new ingest sources especially appreciated.

---

## 🙏 Credits

Built by [@NiteshTechAI](https://x.com/NiteshTechAI).

Inspired by [NicholasSpisak/second-brain](https://github.com/NicholasSpisak/second-brain), [swyx/brain](https://github.com/swyxio/brain), and [Andrej Karpathy](https://x.com/karpathy).

Powered by [Ollama](https://github.com/ollama/ollama), [Gemma 3](https://huggingface.co/google/gemma-3-4b-it), [Poppler](https://poppler.freedesktop.org), [pypdf](https://github.com/py-pdf/pypdf), [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api), and [Obsidian](https://obsidian.md).

---

## 📄 License

MIT — free to use, modify, and share. If you build something cool with it, tag [@NiteshTechAI](https://x.com/NiteshTechAI) on X.

---

<div align="center">

**⭐ Star this repo if it helps you organize your knowledge.**

</div>
