<div align="center">

# 🧠 Second Brain AI

### An always-on AI agent that reads your articles, videos, and tweets, files them into a self-organizing Obsidian wiki, and lets you query the result in plain English from any device.

**Paste a link to a Discord bot. Wake up to a connected knowledge graph. Your laptop can stay off.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Linux VPS](https://img.shields.io/badge/Runs%20on-Linux%20VPS-green)](#)
[![Hermes](https://img.shields.io/badge/Agent-Hermes-purple)](https://github.com/NousResearch/hermes-agent)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20Flash-blue)](https://deepseek.com)
[![Obsidian](https://img.shields.io/badge/Viewer-Obsidian-purple)](https://obsidian.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**[Why](#why-this-exists)** ·
**[Quick start](#-quick-start)** ·
**[Capture paths](#-capture-paths)** ·
**[Cost](#-cost)** ·
**[Architecture](docs/ARCHITECTURE.md)** ·
**[Knowledge model](docs/KNOWLEDGE_MODEL.md)** ·
**[Security](docs/SECURITY.md)**

</div>

---

## Why this exists

Most knowledge tools are write-only. You save bookmarks, drop notes, organize folders. The information piles up, but nothing connects to what you read last month. A year later, you can't find the one thread that mattered.

This project flips the model: **an AI agent maintains your knowledge base for you.** You feed it links from anywhere — Discord, a browser clipper, a drop-in folder. It reads the source, extracts entities and concepts, cross-links them to what already exists, resolves contradictions when new information conflicts with old, and logs every change.

You read the result in Obsidian, or query it in plain English by messaging a Discord bot from your phone.

Pattern inspired by Andrej Karpathy's [LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), extended along four axes:

1. **Always-on hosting** — runs 24/7 on a small Linux VPS, not on your laptop
2. **Multi-source capture** — articles, PDFs, video transcripts, X posts and bookmarks, drop-in files
3. **Agentic curation** — the agent resolves contradictions, tracks when facts were true ([bi-temporal](docs/KNOWLEDGE_MODEL.md#1-bi-temporal-facts)), writes Architecture Decision Records, links into existing pages instead of duplicating
4. **Ambient query** — you talk to it via Discord, on any device, in plain English

Total monthly cost runs **~$8–$15** for a single-person setup.

---

## ⚡ How it works

```
1. CAPTURE   →  how things enter the brain (5 paths into raw/)
2. PIPELINE  →  watcher → kanban → dispatcher → agent (24/7 on VPS)
3. AGENT     →  Hermes runtime + LLM + skills + tools (the brain)
4. VAULT     →  markdown wiki (source of truth)
```

This is a real agent loop, not a fixed script. Per ingest, the agent runs
**observe → plan → act → reason → persist → repeat** (typically 5–15 tool
calls per source). It self-corrects on failure: if a fetch times out, the
file stays in `raw/`, the watcher requeues it, the next run completes it.

**Full architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · **Visual diagram:** [`docs/diagrams/architecture.html`](docs/diagrams/architecture.html)

---

## 🚀 Quick start

Self-hosted system. You'll need a small Linux server, a Discord bot, and an LLM API key. Plan ~30 minutes for the first install.

### Prerequisites

- **VPS** — Ubuntu 22.04+, minimum 4 GB RAM (8 GB if you'll transcribe video on the VPS), ~20 GB disk
- **Discord bot** — create one at [discord.com/developers/applications](https://discord.com/developers/applications), invite to a server you own
- **LLM API key** — DeepSeek (cheapest), OpenRouter (flexible), or Anthropic (strongest reasoning)
- **Optional:** residential proxy (~$5 one-time for 5 GB) if you want to ingest YouTube/TikTok directly from the VPS — datacenter IPs are blocked by those platforms

### Install on the VPS

```bash
# 1. Install the Hermes agent runtime
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. Clone this repo, install vault-side deps
git clone https://github.com/<your-username>/second-brain-ai.git /opt/second-brain-ai
cd /opt/second-brain-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-vps.txt
sudo apt install -y inotify-tools ffmpeg

# 3. Follow the full step-by-step runbook
cat deploy/vps/README.md
```

**[`deploy/vps/README.md`](deploy/vps/README.md)** is the long-form deployment guide. It covers the agent profile setup, the systemd services, gateway lockdown, the obsidian MCP wiring, the optional proxy, and the X API auth modes.

### Optional: Mac capture bridge

If you want one-click clipping from Chrome (via the Obsidian Web Clipper extension):

```bash
brew install fswatch
# See deploy/mac/README.md for the full setup
```

Details: **[`deploy/mac/README.md`](deploy/mac/README.md)**

---

## 📥 Capture paths

Five ways to feed the brain. Pick whichever fits your workflow — you don't need all of them.

| Source | How to capture | Notes |
|--------|---------------|-------|
| **Articles · blogs · docs · gists · PDFs** | DM the link to the Discord bot | `web_extract` handles fetching. Works from any device. |
| **Local files** (`.md`, `.txt`, `.pdf`) | Drop into `raw/` on the VPS | Useful for batch backfills. |
| **Browser one-click** | Obsidian Web Clipper → local `raw/` → fswatch → VPS | Best for staying in flow. See [`deploy/mac/`](deploy/mac/). |
| **Video** (YouTube · TikTok · IG · podcasts · 1000+ yt-dlp sites) | Paste link to bot, or run `scripts/clip.py <url>` | YouTube tries captions first (fast, exact), falls back to local CPU whisper. |
| **X / Twitter** | Ask the bot ("search X for X", "save this thread", "show my bookmarks") | `xurl` CLI. Three auth modes covered: bearer (search), OAuth1 (timeline), OAuth2 (bookmarks). |

All five paths converge on a single drop zone (`raw/`). The watcher detects new files, the dispatcher queues an ingest task, the agent runs, processed files move to `raw/processed/`.

---

## 🧠 What the agent writes

Structured markdown with frontmatter that captures both content and provenance:

```yaml
---
confidence: high | medium | low
explored: false
valid_from: YYYY-MM-DD       # when the claim became true in the world
learned_on: YYYY-MM-DD       # when this vault first recorded it
last_verified: YYYY-MM-DD    # last time a re-ingest confirmed it
superseded_by: [[New Page]]  # optional
contradicts: [[Other Page]]  # optional
sources: [path/to/source.md, ...]
---
```

Three patterns differentiate this from a notes app:

- **[Bi-temporal facts](docs/KNOWLEDGE_MODEL.md#1-bi-temporal-facts)** — tracks *when something was true* separately from *when you learned it*. Time-travel queries; automatic drift detection (`last_verified > 180d` → re-check).
- **[Contradiction auto-resolve](docs/KNOWLEDGE_MODEL.md#2-contradiction-auto-resolve)** — when new info conflicts with old, the agent picks a winner, rewrites the page, moves loser content to `## Superseded`, and logs the change.
- **[Decision Records (ADRs)](docs/KNOWLEDGE_MODEL.md#3-decision-records-adrs)** — when the agent helps you pick between alternatives, it writes a lightweight ADR to `wiki/decisions/` so future-you can answer "why did I build it this way?"

Full schema and rationale: **[`docs/KNOWLEDGE_MODEL.md`](docs/KNOWLEDGE_MODEL.md)**

---

## 💰 Cost

| Component | Light use | Heavier use (daily ingest + frequent queries) |
|-----------|-----------|------------------------------------------------|
| LLM (DeepSeek Flash, auto-cached) | < $1/mo | $2 – $5/mo |
| VPS (small KVM, 2 vCPU / 8 GB) | $5 – $8/mo | $5 – $8/mo |
| Residential proxy (only if ingesting video on VPS) | $0 (skip) | ~$5 one-time, 5 GB never-expires |
| Discord bot | $0 | $0 |
| X API (pay-as-you-go) | $0 | $1 – $3/mo |
| **Total** | **~$8/mo** | **~$15/mo** |

The LLM is the variable. Swapping DeepSeek for Claude or GPT-4 multiplies the LLM bill 5–10×.

---

## 🔒 Security model (summary)

- **Code in git, secrets on the server.** API keys, bot tokens, proxy creds live in `~/.hermes/profiles/<profile>/.env` (chmod 600). Never committed.
- **`.gitignore`** blocks `.env`, `*.env`, the vault itself.
- **Pre-commit hook** scans diffs for API-key patterns. Enable: `git config core.hooksPath .githooks`.
- **Gateway lockdown** — `gateway.allow_all_users: false` + Discord ID allowlist. Only authorized users can drive the bot.

Full details, rotation steps, and threat model: **[`docs/SECURITY.md`](docs/SECURITY.md)**

---

## 📚 Documentation

| Document | Covers |
|----------|--------|
| **[Architecture](docs/ARCHITECTURE.md)** | The four layers, agent loop, component responsibilities, services |
| **[Knowledge model](docs/KNOWLEDGE_MODEL.md)** | Page schema, bi-temporal facts, contradiction resolve, ADRs, graphify bridge |
| **[Security](docs/SECURITY.md)** | Secrets model, gateway lockdown, rotation, threat model |
| **[Design notes](docs/DESIGN.md)** | What's intentionally not included (no vector DB, no bidirectional sync, no multi-user) and why |
| **[Repository layout](docs/REPO_LAYOUT.md)** | Annotated file tree, reading order for new contributors |
| **[VPS deployment runbook](deploy/vps/README.md)** | Full step-by-step server install |
| **[Mac capture bridge](deploy/mac/README.md)** | Optional browser-clipper → VPS pipeline |
| **[Architecture diagram](docs/diagrams/architecture.html)** | Single-file visual overview |

---

## 📖 Inspiration

- **[Karpathy's LLM-Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — the foundational pattern (three layers, agent-as-librarian, markdown as the database)
- **[eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)** — a Claude Code skill-pack take on the same idea; bi-temporal facts and contradiction-resolve patterns here are adapted from there
- **[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)** — the agent framework this project is built on

---

## 🤝 Contributing

Issues and PRs welcome. Areas where outside contributions would be especially useful:

- More capture-source adapters (Reddit, LinkedIn, RSS, email)
- Alternative LLM provider examples (Claude, Gemini, local Ollama)
- A web-based query UI for users who don't want Discord
- Better lint rules (richer orphan/drift detection)
- Tests

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

MIT. Fork it, ship your version, send it back if you build something interesting.
