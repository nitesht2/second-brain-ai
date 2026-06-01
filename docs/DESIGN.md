# Design notes — what's intentionally not included

A few design choices that may surprise you and the reasoning behind each.

## No vector database, no RAG

The wiki *is* the retrieval surface.

At personal-KB scale (hundreds to low thousands of pages), an LLM-maintained
markdown index plus graph search beats embeddings on quality and cost:

- **Quality:** the agent has already compressed the source into a structured
  page with explicit `[[wikilinks]]` to related content. Embeddings retrieve
  *similar* text; the wiki retrieves *connected knowledge*.
- **Cost:** no embedding API calls per ingest, no vector DB to host, no
  re-embedding on schema changes.
- **Auditability:** every retrieval path is a wikilink you can trace by hand.
  Vector search is an opaque cosine-similarity.

`obsidian_mcp.py` exposes graph reads (`get_backlinks`, `get_outlinks`,
`find_path`, `search_vault`, `get_hub_notes`) — not vector search. The agent
uses these like a librarian uses a card catalog.

When this trade-off would flip: somewhere north of ~10,000 pages, or when you
have unstructured raw content the agent has *not* curated. Then RAG starts to
help. Personal use rarely gets there.

## No bidirectional sync between Mac and VPS

Capture is one-way: Mac → VPS push (via fswatch + SCP, see [`../deploy/mac/`](../deploy/mac/)).

The VPS vault is the source of truth. Reasons:

- The agent writes to the vault from many concurrent contexts (watcher, gateway,
  heartbeat). Bidirectional sync invites merge conflicts on every agent run.
- The Mac role is *capture*, not *edit*. You don't hand-edit pages mid-session.
- If you want the vault visible on your Mac for Obsidian reading, set up a
  periodic pull (one-way the other direction) or Syncthing in send-only mode.

The vault is plain markdown — you can always `rsync` a snapshot to read locally.
What you should not do is have the Mac copy diverge with edits while the agent
is also writing.

## No phone-side Obsidian sync required

Query happens over Discord, which works on any device. Mobile Obsidian is
optional, not load-bearing.

This decision matters because Obsidian Sync (their paid service) and Syncthing
on iOS are both painful in different ways. Skipping mobile sync entirely sidesteps
the whole mess. If you want a clean reading view on your phone, ask the bot
("show me my latest synthesis on X") — the agent reads the file and replies.

## No web UI

Hermes ships one (`hermes dashboard`), but for a single-person second brain,
Discord plus Obsidian covers every interaction:

- **Ingest / query:** Discord (mobile and desktop)
- **Visual graph / deep read:** Obsidian (desktop)
- **Code-driven edits:** ssh into the VPS, edit the file, the agent will
  reconcile on next ingest

Building a web UI would add another deployment target (HTTPS, auth, sessions)
without unlocking a use case the current surfaces don't cover. Skip until the
need is real.

## No multi-user support

The gateway allowlist (`DISCORD_ALLOWED_USERS`) is set up for one human.

Multi-tenant use would require:

- Per-user Hermes profiles (each with their own LLM key, X tokens, vault)
- Per-user vaults with isolated kanban boards
- Auth on the gateway routing each user to their profile
- Rate limits per user

That's a different product. Out of scope for this template.

## No fallback LLM chain by default

Earlier versions had `fallback_providers:` configured (DeepSeek primary, then
OpenRouter, then local Ollama). Removed for two reasons:

- **Cost isolation:** the project-scoped key for this profile should be the
  only one billing for this brain. A fallback to a shared key blurs that.
- **Failure visibility:** when the primary fails, you want to know immediately
  (so you can rotate the key, switch model, fix the issue). A silent fallback
  hides the problem.

The trade-off: if DeepSeek has an API outage, your brain pauses until it's back.
For a personal KB this is acceptable; for production use, add fallbacks back.

## No auto_ingest.py in the active path

`auto_ingest.py` exists as a deterministic fallback ingest script. It runs one
LLM call per file, no agent loop, no contradiction resolve. Kept in the repo
as reference, but the agentic path (watcher → kanban → llm-wiki skill) is the
primary worker.

Reasons to keep it around:

- Bootstrap a vault from a large backlog without paying for agent loops on
  every file.
- Emergency ingest if Hermes is unavailable.
- Reference implementation of the underlying writeup format.

If you fork and don't need it, delete `auto_ingest.py` — nothing depends on it.

## No graphify in the agent's auto-write path

graphify is invoked manually (or by a project hook) to maintain
`graphify-out/GRAPH_REPORT.md`. The agent *reads* the graph for codebase
questions but does not *generate* it. Reasons:

- Graphify is its own tool with its own update lifecycle.
- Running graphify per agent invocation would multiply ingest cost.
- The graph belongs to the source repo, not the second-brain vault.

The agent treating graphify as a passive index it consults — not a service it
runs — is the right separation.
