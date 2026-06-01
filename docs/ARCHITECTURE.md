# Architecture

Deep reference for how the system is structured. The [README](../README.md) has the high-level
pitch; this doc has the layer-by-layer detail. Visual diagram: [`diagrams/architecture.html`](diagrams/architecture.html).

## The four layers

```
1. CAPTURE   →  how things enter the brain (5 paths into raw/)
2. PIPELINE  →  watcher → kanban → dispatcher → agent (24/7 on VPS)
3. AGENT     →  Hermes runtime + LLM + skills + tools (the brain)
4. VAULT     →  markdown wiki (source of truth)
```

Each layer is independently replaceable. Swap the LLM without touching capture.
Swap the runtime and the vault stays valid markdown. Swap the gateway from Discord
to Telegram and capture/pipeline are unchanged.

## The agent loop (what "agentic" means in this codebase)

This isn't a fixed script that calls one LLM per file. The agent runs a true
reason-act loop per ingest:

1. **Observe.** Reads the new source plus the existing `index.md`, `SCHEMA.md`,
   and recent `log.md` entries. Establishes context before doing anything.
2. **Plan.** Chooses tools based on the URL type — `web_extract` for articles,
   `clip.py` for video, `xurl` for tweets, `search_vault` to check for duplicates.
3. **Act.** Calls the tool, reads the result.
4. **Reason.** Decides whether to create a new page, append to an existing one,
   or resolve a contradiction. Cross-links to related notes.
5. **Persist.** Writes the wiki pages, updates the index, logs the action.
6. **Repeat.** Loops until the task is complete, then reports back.

Typical ingest spans 5–15 tool calls per source. The agent self-corrects on
failure — if a fetch times out, the file stays in `raw/`, the watcher requeues
it, the next agent run completes it.

## Components and responsibilities

| Layer | Component | Role |
|-------|-----------|------|
| **Agent runtime** | [Hermes Agent](https://github.com/NousResearch/hermes-agent) | Owns the agent loop, profile isolation, session memory, gateway connections, kanban orchestration, MCP plumbing |
| **LLM (reasoning)** | DeepSeek V4 Flash (default) | The model that thinks. Swappable to Claude / OpenAI / OpenRouter / local Ollama via one config change |
| **Knowledge skill** | `llm-wiki` (bundled with Hermes) | Encodes the ingest-curate-query workflow: orient first, check for duplicates, cross-link, resolve contradictions |
| **Vault tools** | Custom `obsidian_mcp.py` (in this repo) | Graph reads: backlinks, outlinks, neighbors, find-path, hub-detection, vault search |
| **Web tools** | `web_extract` · `duckduckgo-search` · `scrapling` | Article fetching, web search, stealth scraping |
| **Video tools** | `yt-dlp` · `faster-whisper` · `youtube-transcript-api` | Download audio, prefer existing captions, fall back to CPU transcription |
| **Social tools** | `xurl` | Official X API access — search, read, bookmarks, timeline |
| **Gateway** | Hermes Discord gateway | The bot you message. Same process embeds the kanban dispatcher |
| **Persistence** | Plain markdown + SQLite (kanban) | No vector DB. The wiki *is* the retrieval surface |

## Why this stack

- **Hermes** handles the parts that take weeks to build right: agent loops, MCP, gateway,
  profile isolation, session memory, kanban orchestration. Weekend project, not a quarter.
- **DeepSeek Flash** is the cheapest credible reasoner with server-side prompt caching
  — the agent sends the same large preamble (SCHEMA + index + skill prompt) per ingest,
  so caching cuts marginal cost dramatically. Swap to Claude or GPT-4 if you want
  stronger reasoning and don't mind paying 5–10×.
- **Markdown + Obsidian** keeps your data portable. No vendor lock-in. If the agent
  ever stops running, the wiki is still a regular Obsidian vault on disk.
- **A small VPS** ($5–$8/mo) is sufficient. The agent is bursty, not constant.

## Services on the VPS (systemd)

| Unit | Purpose | Schedule |
|------|---------|----------|
| `hermes-gateway-secondbrain-agent` | Discord bot + embedded kanban dispatcher | Always on |
| `secondbrain-watcher` | inotify on `raw/` → creates ingest task per new file | Always on |
| `secondbrain-heartbeat.timer` | Daily sweep + lint (orphans, broken links, stale facts) | 04:07 UTC, daily |

Template unit files live in [`../deploy/vps/`](../deploy/vps/). Copy, edit, install, enable.

**Important:** the watcher and dispatcher must not race. The gateway has an
embedded dispatcher; if you also run a standalone `kanban daemon`, both will
try to claim the same tasks. Pick one — gateway-embedded is the recommended
setup (you get Discord plus dispatch in one process).

## Related deep-dive docs

- [Knowledge model](KNOWLEDGE_MODEL.md) — page anatomy, bi-temporal facts, contradiction resolve, ADRs
- [Security](SECURITY.md) — secrets/code separation, gateway lockdown, verification
- [Design notes](DESIGN.md) — intentionally-not-included choices and rationale
- [Repository layout](REPO_LAYOUT.md) — annotated file tree
- [VPS deployment runbook](../deploy/vps/README.md) — step-by-step install
