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
**[How it works](#-how-it-works)** ·
**[Architecture](docs/diagrams/architecture.html)** ·
**[Quick start](#-quick-start)** ·
**[Capture paths](#-capture-paths)** ·
**[Knowledge model](#-knowledge-model)** ·
**[Cost](#-cost)** ·
**[Security](#-security-model)**

</div>

---

## Why this exists

Most knowledge tools are write-only. You save bookmarks, drop notes, organize folders. The information piles up, but nothing connects to what you read last month. A year later, you can't find the one thread that mattered.

This project flips the model: **an AI agent maintains your knowledge base for you.** You feed it links from anywhere — Discord, a browser clipper, a drop-in folder. It reads the source, extracts entities and concepts, cross-links them to what already exists, resolves contradictions when new information conflicts with old, and logs every change.

You read the result in Obsidian, or query it in plain English by messaging a Discord bot from your phone.

The pattern is Andrej Karpathy's [LLM-Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea, extended along four axes:

1. **Always-on hosting** — runs 24/7 on a small Linux VPS, not on your laptop
2. **Multi-source capture** — articles, PDFs, YouTube/TikTok/podcast transcripts, X posts and bookmarks, drop-in files
3. **Agentic curation** — the agent resolves contradictions, tracks when facts were true (bi-temporal), writes Architecture Decision Records, and links into existing pages instead of duplicating
4. **Ambient query** — you talk to it via Discord, on any device, in plain English

Total monthly cost runs ~$8–$15 for a single-person setup.

---

## ⚡ How it works

Four layers, each independently replaceable:

```
┌───────────────────────────────────────────────────────────────────┐
│  1. CAPTURE       (how things enter the brain)                     │
│                                                                    │
│   • Discord       → DM the bot a link, or "save this thread"      │
│   • Browser       → Obsidian Web Clipper → file watcher → VPS     │
│   • Files         → drop .md / .pdf / .txt into raw/              │
│   • Video         → yt-dlp + faster-whisper (captions when avail) │
│   • Tweets        → xurl CLI (search · read · bookmarks)          │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│  2. PIPELINE      (runs on the VPS, 24/7)                          │
│                                                                    │
│   inotify watcher → kanban task → dispatcher → spawn agent        │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│  3. AGENT         (the brain)                                      │
│                                                                    │
│   Hermes Agent runtime + LLM (DeepSeek Flash by default)          │
│   + llm-wiki skill + obsidian-graph MCP                           │
│   + tool registry (web_extract, xurl, scrapling, search, ...)     │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│  4. VAULT         (markdown — the source of truth)                 │
│                                                                    │
│   wiki/{entities, concepts, sources, synthesis, decisions, ...}   │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                         QUERY LAYER
            Discord (any device) · Obsidian (graph view)
```

Full architecture diagram: **[`docs/diagrams/architecture.html`](docs/diagrams/architecture.html)** (single self-contained file, opens in any browser).

### What "agentic" means here

This isn't a fixed script that calls one LLM per file. It is a full agent loop:

1. **Observe.** The agent reads the new source plus the existing index, schema, and recent log.
2. **Plan.** It chooses tools based on the URL type — `web_extract` for articles, `clip.py` for video, `xurl` for tweets, `search_vault` to check for duplicates.
3. **Act.** Calls the tool, reads the result.
4. **Reason.** Decides whether to create a new page, append to an existing one, or resolve a contradiction. Cross-links to related notes.
5. **Persist.** Writes the wiki pages, updates the index, logs the action.
6. **Repeat.** Loops until the task is complete, then reports back.

Typical ingest spans 5–15 tool calls per source. The agent self-corrects on failure — if a fetch times out, the file stays in `raw/`, the watcher requeues it, the next agent run completes it.

---

## 📐 Architecture

### Components and their responsibilities

| Layer | Component | Role |
|-------|-----------|------|
| **Agent runtime** | [Hermes Agent](https://github.com/NousResearch/hermes-agent) | Owns the agent loop, profile isolation, session memory, gateway connections, kanban orchestration, MCP plumbing |
| **LLM (reasoning)** | DeepSeek V4 Flash (default) | The model that thinks. Swappable to Claude / OpenAI / OpenRouter / local Ollama via one config change |
| **Knowledge skill** | `llm-wiki` (bundled with Hermes) | Encodes the ingest-curate-query workflow. Tells the agent to orient first, check for duplicates, cross-link, resolve contradictions |
| **Vault tools** | Custom `obsidian_mcp.py` (in this repo) | Graph reads: backlinks, outlinks, neighbors, find-path, hub-detection, vault search |
| **Web tools** | `web_extract` · `duckduckgo-search` · `scrapling` | Article fetching, web search, stealth scraping for IP-tolerant sites |
| **Video tools** | `yt-dlp` · `faster-whisper` · `youtube-transcript-api` | Download audio, prefer existing captions, fall back to local CPU transcription |
| **Social tools** | `xurl` | Official X API access — search, read, bookmarks, timeline |
| **Gateway** | Hermes Discord gateway | The bot you message. Same process embeds the kanban dispatcher |
| **Persistence** | Plain markdown + SQLite (kanban) | No vector DB. The wiki *is* the retrieval surface |

### Why this stack

- **Hermes** handles the parts that take weeks to build right: agent loops, MCP, gateway, profile isolation, session memory, kanban orchestration. A weekend project, not a quarter.
- **DeepSeek Flash** is the cheapest credible reasoner with server-side prompt caching — the agent sends the same large preamble (SCHEMA + index + skill prompt) per ingest, so caching cuts the marginal cost dramatically. Swap to Claude or GPT-4 if you want stronger reasoning and don't mind paying 5–10×.
- **Markdown + Obsidian** keeps your data portable. No vendor lock-in. If the agent ever stops running, the wiki is still a regular Obsidian vault on disk.
- **A small VPS** ($5–$8/mo) is sufficient. The agent is bursty, not constant.

---

## 🚀 Quick start

This is a self-hosted system. You will need a small Linux server, a Discord bot, and an LLM API key. Plan on ~30 minutes for the first install.

### Prerequisites

- **VPS:** Ubuntu 22.04+ (or any modern Linux). Minimum 4 GB RAM, 8 GB recommended if you'll transcribe videos on the VPS. Disk ~20 GB.
- **Discord bot:** create one at [discord.com/developers/applications](https://discord.com/developers/applications), copy the bot token, invite it to a server you own.
- **LLM API key:** pick one provider — DeepSeek (cheapest), OpenRouter (most flexible), Anthropic (strongest reasoning). Note the key.
- **Optional — residential proxy:** only needed if you want to ingest YouTube/TikTok directly from the VPS. Datacenter IPs are blocked by these platforms for scraping. Cost: ~$5 for 5 GB pay-as-you-go, lasts months for audio-only.
- **Optional — Obsidian app** for the graph-view reading layer. Free, available on every OS.

### 1. Install Hermes on the VPS

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

This installs Hermes Agent (Python 3.11+) into `/usr/local/lib/hermes-agent` and puts the `hermes` CLI on your PATH.

### 2. Clone this repo and install the vault-side dependencies

```bash
git clone https://github.com/<your-username>/second-brain-ai.git /opt/second-brain-ai
cd /opt/second-brain-ai
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-vps.txt
```

`requirements-vps.txt` installs `faster-whisper` (CPU transcription), `yt-dlp`, and `youtube-transcript-api`.

Also install `inotify-tools` (`sudo apt install inotify-tools`) and `ffmpeg` (`sudo apt install ffmpeg`).

### 3. Create the vault

The vault is a regular folder with a Karpathy-style layout. The setup script in `setup.sh` will scaffold one for you, or copy `vault-template/` to your chosen location and point `WIKI_PATH` at it.

### 4. Follow the full runbook

Everything else — the agent profile, the systemd services, the Discord gateway, optional xurl + proxy — is detailed step by step in:

**[`deploy/vps/README.md`](deploy/vps/README.md)**

The runbook covers:

- creating a 4 GB swap file (OOM insurance on small VPS)
- adding the secret-loading drop-in to the systemd unit (Hermes regenerates the unit, so an `EnvironmentFile=` override is required)
- locking the gateway (`allow_all_users: false` + Discord-ID allowlist)
- creating the `secondbrain-agent` profile and wiring the obsidian MCP into the profile's isolated `HOME`
- enabling the three services: `secondbrain-watcher`, embedded gateway dispatcher, `secondbrain-heartbeat.timer`
- optional X API setup (bearer token for search, OAuth1 for timeline, OAuth2 for bookmarks — three different scopes, three different auth modes)
- optional residential proxy wiring for video clipping

### 5. (Optional) Mac-side capture bridge

If you also want one-click clipping from Chrome using the Obsidian Web Clipper extension:

```bash
brew install fswatch
cp deploy/mac/com.secondbrain.macpush.plist ~/Library/LaunchAgents/
# edit the plist + watcher script to point at your VPS, then:
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.secondbrain.macpush.plist
```

Configure the Obsidian Web Clipper to save into your local vault's `raw/` folder. The watcher pushes each new file to the VPS automatically via SCP.

Full details: **[`deploy/mac/README.md`](deploy/mac/README.md)**.

---

## 📥 Capture paths

Five ways to feed the brain. Pick whichever fits your workflow — you don't need all of them.

| Source | How to capture | What the agent does with it |
|--------|---------------|-----------------------------|
| **Articles · blog posts · docs · gists · PDFs** | DM the link to the Discord bot, *or* drop the URL in any chat the bot has access to | `web_extract` fetches clean markdown, the agent decides whether to create a source page, an entity page, or a concept page, and cross-links to existing notes |
| **Local files** (`.md`, `.txt`, `.pdf`) | Drop into `raw/` on the VPS directly | Same ingest pipeline — inotify watcher picks them up |
| **Browser one-click** | Obsidian Web Clipper → local `raw/` folder → fswatch → SCP to VPS | Designed for staying in flow. No app-switching while you read |
| **Video** (YouTube, TikTok, Instagram, podcasts, 1000+ yt-dlp-supported sites) | Paste link to Discord bot, *or* run `scripts/clip.py <url>` on the VPS | YouTube: tries captions first (instant, exact). Other sites or captions-disabled: yt-dlp pulls audio, faster-whisper transcribes locally on CPU. Transcript becomes a `sources/` page |
| **X / Twitter** | Ask the bot in plain English: "search X for *X*", "save this thread", "show my bookmarks" | Routes through `xurl` (official X API). Tweet content lands in `sources/`, mentioned tools/people become entity pages |

All five paths converge on a single drop zone (`raw/`). The inotify watcher detects new files, the dispatcher queues an ingest task, the agent runs, and processed files move to `raw/processed/`.

---

## 🧠 Knowledge model

The agent doesn't dump unstructured text. Every wiki page follows a schema designed for compounding knowledge.

### Page anatomy

Concept and entity pages carry frontmatter that captures both content and provenance:

```yaml
---
confidence: high | medium | low
explored: false
valid_from: YYYY-MM-DD       # when the claim became true in the world
learned_on: YYYY-MM-DD       # when this vault first recorded it
last_verified: YYYY-MM-DD    # last time a re-ingest confirmed the claim
superseded_by: [[New Page]]  # optional — set when a newer claim replaces this one
contradicts: [[Other Page]]  # optional — set when two pages disagree
sources: [path/to/source.md, ...]
---
```

The body follows an "evergreen note" structure:

```
# Page Title

## The Idea
One clear statement, written to be useful 12 months from now.

## Why It Matters
What it changes about how the reader works or thinks. Specific, not generic.

## Counter-arguments
At least one. What might the source be missing? What would a skeptic say?

## Connections
- [[Related Page A]]
- [[Related Page B]]
- An open question this opens up.
```

This format forces the agent to write notes that hold up over time, not stream-of-consciousness summaries.

### Three knowledge patterns

These are what differentiate a real second brain from a folder full of summaries.

**1. Bi-temporal facts.** Each page tracks *when something was true in the world* (`valid_from`) separately from *when the vault learned it* (`learned_on`). A 2024 fact ingested in 2026 has `valid_from: 2024, learned_on: 2026`. This enables time-travel queries ("what did I know about X as of last March?") and surfaces stale knowledge automatically — if `last_verified` is more than 180 days old, the next mention triggers a re-check.

**2. Contradiction auto-resolve.** When a new source disagrees with an existing page, the agent doesn't shrug and flag it for you. It compares `valid_from` dates and source weight, picks a winner, rewrites the page, moves the loser to a `## Superseded` section with date and reason, and logs the change in `log.md`. Only when the conflict is truly context-dependent (two valid strategies, two opinions) does it keep both pages alive and link them via `contradicts:` cross-references. Lint surfaces these for review.

**3. Decision Records (ADRs).** When the agent helps you pick between real alternatives — which tool, which architecture, which strategy — it writes a lightweight ADR to `wiki/decisions/` capturing the context, the options considered, the choice, the trade-offs, and a "revisit when" trigger. Future-you can answer "why did I build it this way?" months later.

### Bonus: graphify bridge

If your projects use [graphify](https://github.com/<...>) (or any AST-graph generator), the agent reads `graphify-out/GRAPH_REPORT.md` before grepping source files. Code-architecture questions get answered from the pre-built graph instead of reconstructing the picture from raw files every time.

Full schema specification: **[`deploy/vps/SCHEMA.template.md`](deploy/vps/SCHEMA.template.md)**.

---

## 📂 Vault layout

```
SecondBrain/
├── raw/                ← drop zone (immutable sources)
│   ├── processed/      ← ingested files, moved here after processing
│   └── generated/      ← daily digests, lint reports
└── wiki/               ← agent-maintained — never edit by hand mid-session
    ├── SCHEMA.md       ← the rules the agent follows
    ├── index.md        ← auto-updated content catalog
    ├── log.md          ← append-only chronological action log
    ├── entities/       ← people · companies · tools · models
    ├── concepts/       ← ideas · frameworks · strategies
    ├── sources/        ← one summary per ingested source
    ├── synthesis/      ← cross-topic patterns ("Synthesis - <Theme>.md")
    ├── decisions/      ← ADRs (auto-written for non-trivial choices)
    ├── episodic/       ← agent session records
    └── projects/       ← synced from project documentation
```

This is a regular Obsidian vault. `[[wikilinks]]` resolve correctly, the graph view works out of the box, Dataview queries run normally. If the agent stops running tomorrow, the vault is still readable and editable.

---

## ⚙️ Services (systemd)

The VPS runs three units that together produce always-on behavior:

| Unit | Purpose | Schedule |
|------|---------|----------|
| `hermes-gateway-secondbrain-agent` | Discord bot + embedded kanban dispatcher | Always on |
| `secondbrain-watcher` | inotify on `raw/` → creates kanban ingest task per new file | Always on |
| `secondbrain-heartbeat.timer` | Daily sweep (catches any stragglers in `raw/`) + lint (orphans, broken links, stale facts) | 04:07 UTC, daily |

Template unit files with placeholder paths and identifiers live in **[`deploy/vps/`](deploy/vps/)**. Copy, edit, install, enable.

The watcher and dispatcher run as **separate** processes for a reason: the gateway's embedded dispatcher races with a standalone `kanban daemon` if both are running. Pick one. If you want pure ingest without Discord, run the standalone. If you want Discord (the recommended setup), let the gateway dispatch.

---

## 💰 Cost

Two realistic scenarios for a single-person setup:

| Component | Light use (few clips/day) | Heavier use (daily ingest + frequent queries) |
|-----------|---------------------------|-----------------------------------------------|
| LLM (DeepSeek Flash, with auto-prompt-caching) | < $1/mo | $2 – $5/mo |
| VPS (small KVM, 2 vCPU / 8 GB) | $5 – $8/mo | $5 – $8/mo |
| Residential proxy (only if ingesting video on the VPS) | skip ($0) | ~$5 one-time, 5 GB pay-as-you-go, never expires |
| Discord bot | $0 | $0 |
| X API (pay-as-you-go) | $0 | $1 – $3/mo if you query often |
| **Total** | **~$8/mo** | **~$15/mo** |

The LLM is the only variable. Swapping DeepSeek for Claude or GPT-4 makes the agent stronger but multiplies the LLM bill 5–10×. For a personal knowledge base, the cheaper model with auto-caching is hard to beat.

---

## 🔒 Security model

This system holds keys (LLM, X, Discord bot, optional proxy) and runs an always-on bot that can act on your behalf. The security boundary is deliberate.

### Separation of code and secrets

- **Code goes in git.** Public-safe. Anyone can read, fork, audit.
- **Secrets stay on the server.** They live in:
  - `~/.hermes/profiles/<profile>/.env` (LLM key, Discord bot token, channel IDs, proxy URL) — `chmod 600`
  - `~/.xurl` (X API credentials managed by the xurl CLI) — `chmod 600`
- **`.gitignore`** blocks `.env`, `*.env`, `.frag`, `*.bak.*`, the vault itself (`/wiki/`, `/raw/`, `/outputs/`).
- **Pre-commit hook** (`.githooks/pre-commit`) scans diffs for OpenAI/Anthropic-style keys and `*_API_KEY=` patterns. Enable with `git config core.hooksPath .githooks`.

### Bot lockdown

The Discord gateway defaults to *deny*:

```yaml
gateway:
  allow_all_users: false
```

Add your Discord user ID to `DISCORD_ALLOWED_USERS` in the profile `.env`. Anyone else who DMs the bot gets refused. There is no auto-approval — even pairing codes are off by default.

### Verification

This repo's history is clean. To verify, run:

```bash
git grep -nIE "sk-[A-Za-z0-9]{20,}|API_KEY\s*=\s*['\"][A-Za-z0-9]" $(git rev-list --all)
```

If you fork, **do not** edit the systemd units or scripts to hardcode credentials. Place them in the gitignored `.env`/`.xurl` files. The systemd drop-in pattern (`EnvironmentFile=`) handles the rest.

---

## 🧪 What's intentionally not included

A few design choices that may surprise you:

- **No vector database, no RAG.** The wiki *is* the retrieval surface. At personal-KB scale (hundreds to low thousands of pages), an LLM-maintained markdown index plus graph search beats embeddings on quality and cost. The `obsidian_mcp.py` MCP exposes graph reads, not vector search.
- **No bidirectional sync between Mac and VPS.** Capture is one-way (Mac → VPS push). The VPS vault is the source of truth. If you want to read the vault on your Mac in Obsidian, periodically pull it or set up Syncthing — but treat the VPS copy as canonical to avoid merge conflicts on agent writes.
- **No phone-side Obsidian sync required.** Query happens over Discord, which works on any device. Mobile Obsidian is optional, not load-bearing.
- **No web UI.** Hermes ships one (`hermes dashboard`), but for a single-person second brain, Discord plus Obsidian covers every interaction.
- **No multi-user support.** The gateway allowlist is set up for one human. Multi-tenant would require profile-per-user and per-user vaults — out of scope for this template.

---

## 🧪 Tech stack

| | |
|---|---|
| **Agent runtime** | [Hermes Agent](https://github.com/NousResearch/hermes-agent), Python 3.11+ |
| **LLM** | DeepSeek V4 Flash (default, direct API) · swappable to OpenRouter, Anthropic, OpenAI, local Ollama via a one-line config change |
| **Vault & reader** | [Obsidian](https://obsidian.md) (free), plain markdown |
| **MCP servers** | Custom `obsidian_mcp.py` (graph reads) + `xurl` + `scrapling` + `duckduckgo-search` |
| **Capture tools** | `yt-dlp` · `faster-whisper` (CPU int8) · `youtube-transcript-api` · `fswatch` (macOS) · `inotify-tools` (Linux) |
| **Transport** | Discord gateway · SCP (Mac → VPS) · residential HTTP proxy (optional, for IP-blocked video sources) |
| **Process management** | systemd (Linux VPS) · launchd (macOS) |
| **Storage** | Markdown files · SQLite (kanban) |
| **License** | MIT |

---

## 📖 Inspiration and prior art

- **[Karpathy's LLM-Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — the foundational pattern. Three layers (raw sources → LLM-maintained wiki → schema), agent-as-librarian, markdown as the database.
- **[eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain)** — a Claude Code skill-pack take on the same idea. The bi-temporal facts and contradiction-resolve patterns in this repo are adapted from there, reframed for an always-on architecture.
- **[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)** — the agent framework this project is built on. Open-source, multi-platform, with first-class kanban, gateway, profile, and MCP support.
- **[Obsidian](https://obsidian.md)** — the reading layer. Free, local-first, no lock-in.

---

## 🛠 Repository layout

```
.
├── README.md                              ← you are here
├── LICENSE
├── CONTRIBUTING.md
├── requirements.txt                       ← base Python deps
├── requirements-vps.txt                   ← VPS-only deps (whisper, yt-dlp, playwright)
├── setup.sh                               ← one-command vault scaffold
├── auto_ingest.py                         ← fallback ingest script (deterministic; the
│                                              agent path is the primary worker)
├── brain_server.py                        ← optional local HTTP server (bookmarklet support)
├── social_downloader.py                   ← legacy Mac-side clipper
├── obsidian_mcp.py                        ← graph-read MCP server for the agent
├── scripts/                               ← clip.py, brain_clip.py, daily_digest.py,
│                                              file_watcher.sh, weekly_review.py
├── deploy/
│   ├── vps/                               ← runbook + systemd units + watcher +
│   │                                          SCHEMA template + clip scripts
│   └── mac/                               ← Mac capture bridge (fswatch + launchd)
├── docs/
│   ├── VPS_DEPLOYMENT.md                  ← long-form deployment notes
│   └── diagrams/architecture.html         ← single-file architecture diagram
├── launchd/                               ← reference plists (older Mac-driven layout)
└── vault-template/                        ← starter vault structure (AGENTS.md, SCHEMA, ...)
```

---

## 🤝 Contributing

Issues and PRs are welcome. The codebase is small and the moving parts are documented. Areas where outside contributions would be especially useful:

- More capture-source adapters (Reddit, LinkedIn, RSS, email)
- Alternative LLM provider examples (Claude, Gemini, local Ollama)
- A web-based query UI for users who don't want Discord
- Better lint rules (richer orphan/drift detection)
- Tests

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 License

MIT. Fork it, ship your version, send it back if you build something interesting.
