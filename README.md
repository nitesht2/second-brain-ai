<div align="center">

# 🧠 Second Brain AI

### An always-on agent that reads your articles, videos, and tweets, files them into a connected Obsidian wiki, and lets you query the result in plain English from your phone.

**Paste a link to your Discord bot. Wake up to a cross-linked knowledge graph. Mac stays off.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Linux VPS](https://img.shields.io/badge/Runs%20on-Linux%20VPS-green)](#)
[![Hermes](https://img.shields.io/badge/Agent-Hermes-purple)](https://github.com/NousResearch/hermes-agent)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20Flash-blue)](https://deepseek.com)
[![Obsidian](https://img.shields.io/badge/Viewer-Obsidian-purple)](https://obsidian.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Why](#why-this-exists) · [Architecture](docs/diagrams/architecture.html) · [Quick start](#-quick-start) · [Capture paths](#-capture-paths) · [Knowledge model](#-knowledge-model) · [Cost](#-cost)

</div>

---

## Why this exists

Bookmarks decay. Notes apps fill up with orphans. Most "second brain" systems are write-heavy: you save things, the knowledge never connects to what you saved last month.

This flips it: an **agent** maintains your wiki for you. You feed it links from anywhere (Discord, a Chrome clipper, drop-in folders). It reads the source, extracts entities and concepts, cross-links them into what already exists, resolves contradictions, and logs the changes. You read the result in Obsidian, or query it in plain English from your phone via Discord.

Inspired by [Andrej Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — extended with always-on hosting, multi-source capture, an agent that resolves contradictions instead of flagging them, and an ambient query layer via Discord.

---

## 📐 Architecture

Three layers, plus a query layer:

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPTURE      (multiple paths into raw/)                         │
│   • Discord  → paste any URL to the bot                          │
│   • Browser  → Obsidian Web Clipper → local watcher → VPS        │
│   • Files    → drop .md / .pdf / .txt into raw/                  │
│   • Video    → yt-dlp + faster-whisper (proxy for IP blocks)     │
│   • Tweets   → xurl (search · read · bookmarks)                  │
├─────────────────────────────────────────────────────────────────┤
│  PIPELINE    (24/7 on the VPS)                                   │
│   inotify watcher → kanban task → agent dispatch → ingest        │
├─────────────────────────────────────────────────────────────────┤
│  AGENT       (the brain)                                         │
│   Hermes Agent + LLM (DeepSeek Flash by default)                 │
│   + llm-wiki skill + obsidian-graph MCP + web search             │
├─────────────────────────────────────────────────────────────────┤
│  VAULT       (markdown — source of truth)                        │
│   wiki/entities · concepts · sources · synthesis · decisions     │
├─────────────────────────────────────────────────────────────────┤
│  QUERY       (anywhere)                                          │
│   Discord (any device) · Obsidian (graph view, optional)         │
└─────────────────────────────────────────────────────────────────┘
```

Full diagram: [`docs/diagrams/architecture.html`](docs/diagrams/architecture.html) (single-file, opens in any browser).

**Tech split:**
- **Agent runtime:** [Hermes Agent](https://github.com/NousResearch/hermes-agent) (handles the agent loop, profile isolation, gateway, kanban, MCP)
- **Reasoning:** any LLM Hermes supports — DeepSeek Flash is the default here for cheap auto-prompt-caching; swappable to Claude / OpenRouter / local Ollama via one config change
- **Knowledge skill:** `llm-wiki` (ships with Hermes) — orient → check existing → cross-link → resolve contradictions → log
- **Vault tools:** custom `obsidian_mcp.py` exposes graph reads (backlinks · outlinks · search · find-path · hubs)

---

## 🚀 Quick start

**Prereqs:**
- A Linux VPS (Ubuntu 22.04+, 4 GB RAM minimum, 8 GB recommended)
- A Discord bot token + a server where you can invite it
- An LLM API key (DeepSeek / OpenRouter / Anthropic — pick one)
- Optional: residential proxy if you want to ingest videos directly from the VPS (YouTube/TikTok block datacenter IPs)

**On the VPS:**

```bash
# 1. Install Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. Clone this repo into the vault root
git clone https://github.com/<you>/second-brain-ai.git /root/SecondBrain
cd /root/SecondBrain
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-vps.txt

# 3. Follow the full setup runbook
cat deploy/vps/README.md
```

The runbook ([`deploy/vps/README.md`](deploy/vps/README.md)) covers:
- swap + permissions baseline
- gateway lockdown (`allow_all_users: false` + Discord ID allowlist)
- importing/creating the `secondbrain-agent` profile
- wiring the obsidian MCP into the profile's home
- installing the systemd services (watcher · dispatch · heartbeat)
- xurl auth (bearer + OAuth1 + OAuth2 for full X coverage)
- proxy setup (optional)

**On the Mac** (only if you want one-click browser clipping):

```bash
brew install fswatch
cp deploy/mac/com.secondbrain.macpush.plist ~/Library/LaunchAgents/
# edit the plist + watcher to point at your VPS, then:
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.secondbrain.macpush.plist
```

Set the Obsidian Web Clipper to save into your local vault's `raw/` folder. The watcher pushes new files to the VPS automatically.

---

## 📥 Capture paths

You don't need all of these — pick the ones that fit how you work.

| Source | Path | Notes |
|--------|------|-------|
| **Any link** (article, blog, docs, gist, PDF) | DM to the Discord bot | Agent uses `web_extract`. Works from phone or desktop. |
| **Local files** (`.md`, `.txt`, `.pdf`) | Drop into VPS `raw/` directly | Useful for batch backfills. |
| **Browser one-click** | Obsidian Web Clipper → local `raw/` → fswatch → VPS | Best for "I'm in flow, don't switch apps." Mac watcher in `deploy/mac/`. |
| **Video** (YouTube · TikTok · IG · podcasts · 1000+ sites) | Paste link to bot, or run `scripts/clip.py <url>` | yt-dlp + faster-whisper. YouTube uses captions first, falls back to whisper. |
| **X / Twitter** | Ask the bot ("search X for …", "save this thread", "show my bookmarks") | `xurl` CLI under the hood. Three auth modes covered: bearer (search), OAuth1 (timeline), OAuth2 (bookmarks). |

`raw/` is the single drop zone. Whatever lands there gets picked up by the watcher → queued as a kanban task → ingested by the agent → moved to `raw/processed/`.

---

## 🧠 Knowledge model

The agent writes structured markdown. Every concept/entity page carries:

```yaml
---
confidence: high | medium | low
explored: false
valid_from: YYYY-MM-DD       # when the claim became true in the world
learned_on: YYYY-MM-DD       # when this vault first recorded it
last_verified: YYYY-MM-DD    # last time a re-ingest confirmed it
superseded_by: [[New Page]]  # optional
contradicts: [[Other Page]]  # optional
---
```

Two patterns make this more than a notes app:

- **Bi-temporal facts:** track *when something was true* separately from *when you learned it*. A 2024 fact ingested in 2026 has `valid_from: 2024`, `learned_on: 2026`. Enables "what did I know and when" queries, and surfaces drift (`last_verified > 180d → re-check`).
- **Contradiction auto-resolve:** when a new source disagrees with an existing page, the agent compares `valid_from` + source weight, picks a winner, rewrites the page, moves the loser to a `## Superseded` section with date + reason, and logs the change. Only truly context-dependent ambiguity stays as a `contradicts:` cross-link.

Plus a lightweight **Decision Records (ADR)** folder for trade-off choices the agent helps you make, and a **graphify bridge** so codebase questions (where is X defined, how does Y work) route through pre-built AST reports instead of grepping source.

Full schema: [`deploy/vps/SCHEMA.template.md`](deploy/vps/SCHEMA.template.md).

---

## 📂 Vault layout

```
SecondBrain/
├── raw/                ← drop zone (immutable sources)
│   ├── processed/      ← ingested files
│   └── generated/      ← daily digests, lint reports
└── wiki/               ← agent-maintained
    ├── SCHEMA.md       ← rules the agent follows
    ├── index.md        ← auto-updated content catalog
    ├── log.md          ← append-only action log
    ├── entities/       ← people · tools · companies · models
    ├── concepts/       ← ideas · frameworks · strategies
    ├── sources/        ← one summary per ingested source
    ├── synthesis/      ← cross-topic patterns
    ├── decisions/      ← ADRs (auto-written for non-trivial choices)
    ├── episodic/       ← agent session records
    └── projects/       ← synced from project docs
```

Standard Obsidian vault — open in Obsidian for the graph view, or browse on GitHub if you sync.

---

## ⚙️ Services (systemd)

| Service | What | When |
|---------|------|------|
| `hermes-gateway-secondbrain-agent` | Discord bot + embedded dispatcher | Always on |
| `secondbrain-watcher` | inotify on `raw/` → creates ingest tasks | Always on |
| `secondbrain-heartbeat.timer` | Daily sweep + lint | 04:07 UTC |

All units (with placeholders) are in [`deploy/vps/`](deploy/vps/).

---

## 💰 Cost

Two scenarios, both real:

| Component | Light use | Heavier use (daily ingest + queries) |
|-----------|-----------|--------------------------------------|
| LLM (DeepSeek Flash, auto-cached) | < $1/mo | $2-5/mo |
| VPS (Hostinger KVM 2 or equivalent) | ~$8/mo | ~$8/mo |
| Residential proxy (only if ingesting video from VPS) | $0 (skip) | ~$5 one-time (5 GB pay-as-you-go) |
| Discord bot | $0 | $0 |
| X API (pay-as-you-go) | $0 | ~$1-3/mo if you query often |
| **Total** | **~$8/mo** | **~$15/mo** |

Cheaper than most note apps' annual plan. The LLM is the variable — swapping to Claude or GPT-4 makes it 5-10× pricier; staying on DeepSeek Flash keeps it negligible.

---

## 🔒 Security model

- **Code in git, secrets on the server.** API keys, bot tokens, and proxy creds live in `~/.hermes/profiles/<profile>/.env` (chmod 600) and `~/.xurl`. None of them are ever committed.
- **`.gitignore` blocks** `.env`, `*.env`, `.frag`, `*.bak.*`, and the vault itself.
- **Gateway lockdown:** `gateway.allow_all_users: false` + a Discord-ID allowlist means only you can drive the bot.
- **Pre-commit secret scan** in `.githooks/pre-commit` (enable with `git config core.hooksPath .githooks`).
- **No secrets in this repo's history.** Verified via full `git rev-list --all` grep.

If you fork, the same boundary applies: place your secrets in the gitignored `.env`/`.xurl`, never edit the unit files or scripts to hardcode them.

---

## 🧩 What's intentionally not here

A few decisions worth calling out:

- **No vector DB / RAG.** The wiki *is* the retrieval surface. Karpathy's argument: at personal-KB scale, an LLM-maintained markdown index + graph search beats embeddings on quality and cost. This system follows that — `obsidian_mcp.py` exposes graph reads, not vector search.
- **No bidirectional sync.** Mac → VPS is one-way (push captures). The VPS vault is the source of truth. If you want the vault visible on your Mac for Obsidian reading, use a periodic pull or Syncthing — but treat the VPS copy as canonical.
- **No phone-side Obsidian sync required.** Query is via Discord (works on any device). Obsidian on your phone is optional, not load-bearing.

---

## 🧪 Tech

| | |
|---|---|
| **Agent runtime** | [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Python 3.11+) |
| **LLM** | DeepSeek V4 Flash via direct API · swappable to OpenRouter, Anthropic, local Ollama |
| **Reader / viewer** | [Obsidian](https://obsidian.md) (free) |
| **MCP** | Custom `obsidian_mcp.py` (graph reads) + xurl + scrapling + duckduckgo-search |
| **Capture** | yt-dlp · faster-whisper (CPU) · youtube-transcript-api · fswatch · inotify-tools |
| **Transport** | Discord (gateway) · scp (Mac→VPS) · residential HTTP proxy (optional) |
| **Process mgmt** | systemd (Linux) · launchd (macOS) |

---

## 📖 Inspiration & related work

- [Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the foundational pattern
- [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) — a Claude Code skill-pack approach with bi-temporal facts and contradiction-resolve (both ideas borrowed here, adapted for the always-on architecture)
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — the agent framework this is built on
- [Obsidian](https://obsidian.md) — the reading layer

---

## 📄 License

MIT. Fork it, ship your version, send it back if you build something neat.
