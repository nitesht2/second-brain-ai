<div align="center">

# 🧠 Second Brain AI

### AI agents that write, maintain, and compound your knowledge base on autopilot.

**Drop files in. Wake up to a connected knowledge graph in Obsidian. $0.04/month.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![macOS](https://img.shields.io/badge/Platform-macOS-lightgrey)](#)
[![DeepSeek](https://img.shields.io/badge/AI-DeepSeek%20Flash-blue)](https://deepseek.com)
[![Obsidian](https://img.shields.io/badge/Viewer-Obsidian-purple)](https://obsidian.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [How It Works](#-how-it-works) • [Cost](#-cost) • [Reference](#-inspiration)

</div>

---

## Why This Exists

Most knowledge tools are write-heavy. You read articles, save bookmarks, organize folders. The knowledge sits there. It never connects to what you learned yesterday.

This flips it: **AI agents write and maintain a persistent Obsidian wiki.** Every file you drop gets ingested. Every agent run gets captured. Every project doc stays synced. The wiki compounds with every cycle. You just read.

Inspired by [Andrej Karpathy's llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) concept and extended with full automation, multi-agent orchestration, and $0.04/month pricing.

---

## 🚀 Quick Start

```bash
git clone https://github.com/nitesht2/second-brain-ai.git
cd second-brain-ai
./setup.sh
```

That's it. The setup script:

1. Creates the vault at `~/SecondBrain/`
2. Installs Python dependencies
3. Sets up 3 launchd services (ingest, file watcher, daily digest)
4. Copies the file watcher and daily digest scripts

**Prerequisites:** macOS, Python 3, Obsidian (free), Homebrew

**After setup:**
1. Open Obsidian → Open folder as vault → select `~/SecondBrain`
2. Drop a markdown file into `~/SecondBrain/raw/`
3. The file watcher picks it up and triggers ingestion
4. Browse `wiki/` in Obsidian to see your knowledge graph

---

## 🏗 Architecture

```
                    ┌─────────────────────────────────────┐
                    │       HERMES AGENT (orchestrator)    │
                    │       Kanban dispatch + cron         │
                    └──────────────┬──────────────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       │                           │                           │
       ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│ 5 Agent      │          │ File Watcher │          │ Cron Jobs    │
│ Profiles     │          │ (fswatch)    │          │ (launchd)    │
│ DeepSeek     │          │ monitors     │          │ 4 services   │
│ Flash        │          │ raw/ dir     │          │ auto-start   │
└──────┬───────┘          └──────┬───────┘          └──────┬───────┘
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │    Knowledge Pipeline    │
                    │    Every 6 Hours         │
                    └───────────┬────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ DISTILL      │       │ INGEST       │       │ SCAN         │
│ episodic/    │       │ raw/         │       │ CLAUDE.md    │
│ session logs │       │ markdown     │       │ README.md    │
│ → concepts   │       │ PDF, text    │       │ → wiki       │
└──────┬───────┘       └──────┬───────┘       └──────┬───────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              │
                              ▼
                    ┌────────────────────────┐
                    │     OBSIDIAN VAULT       │
                    │     ~/SecondBrain/wiki/   │
                    │                          │
                    │  concepts/    synthesis/  │
                    │  entities/    episodic/   │
                    │  sources/     index.md    │
                    └───────────────────────────┘
```

Three layers, exactly as Karpathy described: Raw Sources → LLM-Maintained Wiki → Schema (CLAUDE.md). Extended with full automation.

---

## 📂 How It Works

### Phase 1: Distillation

Every pipeline in the setup writes a session record after finishing. The heartbeat reads them and extracts new concepts, entities, and patterns. The system learns from its own output.

### Phase 2: Ingestion

Drop files into `raw/`. The file watcher (fswatch) detects them instantly and triggers ingestion. The agent reads each file through an LLM, extracts entities and concepts, writes structured wiki entries with Obsidian `[[wikilinks]]`, and updates `index.md`. Processed within minutes.

### Phase 3: Project Sync

Every 6 hours, the agent scans `CLAUDE.md` and `README.md` from your active projects. Changed files get extracted into `wiki/projects/`. Architecture docs stay synced automatically.

### Daily Feed

A Python script calls the GitHub API, Hacker News API, and OpenRouter API at 6 AM. Trending repos, top stories, and model changes go into `raw/generated/`. All deduplicated.

### Weekly Lint

Karpathy recommended periodic wiki health checks. This build automates them. Orphan detection, contradiction flagging, missing concept suggestions, index validation.

### Personalized Curation

The feeds are not generic AI news. Topics are curated to your specific interests and projects:

| Feed | Curated Topics | Why |
|------|---------------|-----|
| Daily digest | AI repos, HN stories, model pricing | Matches your stack: AI agents, automation, content pipelines |
| Weekly scans | 8 hand-picked topics | Your domains: affiliate deals, trading, content creation, Python automation, marketing analytics, building in public, multi-income streams |
| Project sync | Your active project docs | CLAUDE.md and README.md from your own repos |

Every URL is checked against a dedup database. Zero repeats. The feeds evolve with your interests — update the topic list and the next scan reflects it.

### Runs on Autopilot

Four macOS launchd services survive reboot. The file watcher catches new content in real time. The cron heartbeat fires every 6 hours as a reliability fallback. Kanban dispatch via Hermes Agent routes every task to the right agent profile. Observability on every board — status, timestamps, output, assignee. No digging through logs.

---

## 💰 Cost

| Component | Technology | Runs | Cost/mo |
|-----------|-----------|------|---------|
| 5 agent profiles | DeepSeek Flash | Every 6h | $0.03 |
| Orchestration | Hermes Agent kanban | Continuous | $0.00 |
| File watcher | fswatch + launchd | Real-time | $0.00 |
| Daily feed | GitHub/HN/OR APIs | 6 AM daily | $0.00 |
| Weekly scans | Agent browser | Sundays | $0.01 |
| Wiki viewer | Obsidian | As needed | $0.00 |
| Dedup | SQLite | Persistent | $0.00 |
| **Total** | | | **$0.04** |

Cheaper than one ChatGPT Plus month. Runs every day. You read. Agents write.

---

## 📁 Vault Structure

```
~/SecondBrain/
├── CLAUDE.md             ← Agent instructions (schema)
├── raw/                  ← Drop files here for ingestion
│   ├── processed/        ← Ingested files (don't touch)
│   └── generated/        ← Auto-generated digests
├── wiki/
│   ├── index.md          ← Auto-updated table of contents
│   ├── log.md            ← Chronological operation log
│   ├── entities/         ← People, companies, tools
│   ├── concepts/         ← Ideas, frameworks, strategies
│   ├── sources/          ← One summary per ingested file
│   ├── synthesis/        ← Cross-topic patterns
│   ├── episodic/         ← Agent session records
│   └── projects/         ← Auto-synced from CLAUDE.md
├── outputs/              ← Logs, lint reports
├── auto_ingest.py        ← Ingestion engine
└── brain_server.py       ← Save server (bookmarklet)
```

---

## 🔮 Obsidian — The Reading Layer

The wiki is a standard **Obsidian vault**. Every page uses Obsidian-flavored markdown with `[[wikilinks]]`. Karpathy described it best: *"Obsidian is the IDE. The LLM is the programmer. The wiki is the codebase."*

**The agents write everything.** You read it in Obsidian:

- 🕸️ **Graph view** — watch connections form between concepts, entities, and sources as the wiki grows
- 🔗 **Wikilinks** — click any `[[link]]` to jump to a connected page. The LLM maintains all cross-references
- 📋 **Backlinks** — see every page that references the current one. Discover connections you did not know existed
- 🔍 **Search** — full-text search across 270+ interlinked pages

**What you do:** curate sources, drop files into `raw/`, ask questions, browse discoveries.

**What the agents do:** read files, extract entities, write pages, update cross-references, maintain the index, run lint checks, flag contradictions. Everything that makes a knowledge base actually useful over time.

The [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) repo provides MCP-based tools that let Hermes Agent interact with the vault programmatically — reading pages, searching for concepts, checking backlinks. The agents use these during every ingest and lint operation.

---

## 🛠 Components

| File | Purpose |
|------|---------|
| `setup.sh` | One-command install |
| `auto_ingest.py` | Reads raw files, calls LLM, writes wiki entries |
| `brain_server.py` | Local HTTP server for browser bookmarklet saves |
| `scripts/daily_digest.py` | Collects GitHub, HN, OpenRouter data at 6 AM |
| `scripts/file_watcher.sh` | Watches raw/ for new files, triggers kanban |
| `scripts/backup.sh` | Backs up vault to timestamped directory |
| `launchd/` | macOS services: ingest, watcher, daily digest, server |
| `vault-template/` | Empty vault structure + CLAUDE.md schema |

---

## 🤖 Services (launchd)

| Service | When | What |
|---------|------|------|
| `com.secondbrain.ingest` | Daily 4:07 AM | Runs auto_ingest.py |
| `com.secondbrain.watcher` | Real-time | Watches raw/ for new files |
| `com.secondbrain.daily-digest` | Daily 6:00 AM | Runs daily_digest.py |
| `com.secondbrain.server` | Always on | Save server on port 7331 |

All survive reboot. View logs in `~/SecondBrain/outputs/`.

---

## 🧩 Hermes Agent Integration

For the full kanban-orchestrated system with 5 agent profiles on DeepSeek Flash:

```bash
hermes kanban init
hermes kanban create --board secondbrain --title "Ingest" --assignee secondbrain-agent
```

The agents use [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) (MCP-based) to navigate and write to the Obsidian vault programmatically. The LLM handles all cross-referencing, link maintenance, and index updates.

---

## 📖 Inspiration

- [Karpathy's llm-wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the original concept
- [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) — MCP skills for vault interaction
- [Obsidian](https://obsidian.md) — the reading layer
- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — the orchestration layer
- [DeepSeek](https://deepseek.com) — the AI engine

---

## 📄 License

MIT — use it, fork it, ship it. If you build something with this, send it my way.
