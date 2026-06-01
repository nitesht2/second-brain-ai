# VPS Deployment Plan — Second Brain + Hermes Multi-Agent Server

Status: DRAFT for review. Nothing deployed yet.

## Goal

Core motivation: **query the brain any time + keep it always up to date.**
Hermes is the centerpiece — the always-on agent you message (Discord) that reads
the vault and answers. The ingest pipeline keeps its memory fresh.

Move the always-on engine from the Mac to the Linux VPS:

- Second Brain ingest/digest/weekly pipeline runs on the VPS (systemd timers) —
  keeps the vault fresh 24/7.
- Hermes Agent runs as a full multi-agent server on the VPS (secondbrain +
  optional additional project boards), dispatching kanban tasks.
- Hermes Discord gateway = the query layer. Message the bot from iPhone or Mac,
  secondbrain-agent reads the vault (via obsidian_mcp.py + llm-wiki skill) and
  answers. iOS uses the Discord app — no Obsidian-mobile-sync needed for Q&A.
- The Obsidian vault syncs VPS to Mac via Syncthing; Obsidian on the Mac is the
  visual graph layer (bonus, not the query path).

## Query architecture (the point of all this)

```
iPhone / Mac Discord app
   |  "what did I save about X?"
   v
Hermes gateway (VPS, always-on)  -->  secondbrain-agent
   |                                    | obsidian_mcp.py reads VPS vault
   |                                    | llm-wiki skill finds + synthesizes
   <------------------------------------+
   answer in Discord thread

Mac Obsidian  <-- Syncthing --  VPS vault   (visual browsing, optional)
```

Already configured on the Mac (ports to VPS): secondbrain-agent profile with
`obsidian-graph` MCP -> obsidian_mcp.py, llm-wiki + obsidian skills,
DISCORD_WIKI_BOT_TOKEN + DISCORD_WIKI_CHANNEL, dispatch_in_gateway: true.
Missing piece is only the running gateway (config `platforms: {}` today).

## Decisions locked

| Decision | Choice |
|----------|--------|
| Scheduler | systemd timers |
| Read layer | Syncthing -> Mac Obsidian |
| Transcription | CPU whisper on VPS |
| Hermes scope | Full multi-agent server (secondbrain (+ optional additional boards)) |
| Kanban state | Independent VPS instance (recommended; no SQLite sync) |
| Query layer | Hermes Discord gateway (iPhone + Mac); Obsidian = visual bonus |
| Devices | iPhone (Discord app for Q&A) + MacBook (Obsidian + Discord) |
| **Ingest worker** | **FULLY AGENTIC — Hermes secondbrain-agent + llm-wiki skill.** Retire auto_ingest.py as the active worker (keep in repo as fallback/reference). |
| Sync | Syncthing (free). Mac reads vault; iPhone queries via Discord (no iOS Obsidian sync needed). |
| VPS specs | small KVM VPS: 2 vCPU, 8 GB RAM, 100 GB, Ubuntu 24.04 (~3.4 GB already used) |

## Fully-agentic ingest (the model shift)

The `llm-wiki` skill (v2.1.0, already in secondbrain-agent) is a complete
agentic ingest + query + lint engine. It REPLACES the fixed-prompt
auto_ingest.py: the agent orients (reads SCHEMA/index/log), checks existing
pages before writing (dedup-aware), cross-links, handles contradictions, and
maintains index/log. Trigger = watcher -> kanban task -> Hermes dispatches
secondbrain-agent -> agent ingests new raw/ files; plus a cron heartbeat.

Reconciliation work this requires:
1. **Write a custom `SCHEMA.md`** describing the EXISTING vault layout
   (entities/concepts/sources/synthesis/episodic/projects, 376 files) so the
   agent respects current structure — do NOT migrate files to the skill's
   default entities/concepts/comparisons/queries layout.
2. **Set `WIKI_PATH`** env to the vault path on the VPS.
3. **Cost/RAM:** multi-turn agent per source (vs 1 LLM call). Throttle agent
   concurrency on the 8 GB box; cost rises above $0.04/mo but stays low on
   owl-alpha/DeepSeek. daily_digest.py (feed fetcher) and the watcher stay as
   thin scripts that feed raw/; the AGENT does the actual ingest/lint/synthesis.

## Security — RESOLVED on Mac source config (carries to VPS)

`gateway.allow_all_users` and `GATEWAY_ALLOW_ALL_USERS` were `true` (anyone who
could message the bot could query/control the whole agent fleet). Both set to
`false` (backup: `~/.hermes/config.yaml.bak.pre-security-fix`). Access model is
now **pairing**: a user who messages the bot is *pending* until the owner runs
`hermes pairing approve <code>`; everyone else is locked out. On the VPS: DM the
bot once, approve your own pairing, done. HARD GATE before gateway goes public.

## Inputs still needed

1. **VPS specs** — RAM, vCPU, OS/version. Drives whisper model size and whether
   the full agent fleet fits. THIS IS THE GATING UNKNOWN.
2. **Access** — SSH access for live setup, or generate scripts you run yourself.
3. **Provider keys for VPS** — OpenRouter (have it) + DeepSeek + any per-board
   integrations you want live on the VPS (Discord channels). Some can be
   omitted on the VPS to keep it lean.

## RAM budget risk (READ THIS FIRST)

The Mac rule is <20 GB across local processes. A Linux VPS is smaller
(commonly 4-8 GB). The full plan stacks:

- Hermes dispatcher + N agent profiles (each agent run loads a model client;
  concurrent runs multiply memory)
- CPU whisper (`small` ~2-3 GB during transcription, `medium` ~5 GB)
- Syncthing (~150-300 MB)
- Python ingest runs

If the VPS is <= 4 GB, the realistic shape is: text/PDF/URL ingest + Hermes with
**low agent concurrency** + whisper `base`/`small`, transcription serialized.
Confirm specs before committing to `medium` whisper or high concurrency.

## Phased plan

### Phase 0 — Prep (no VPS changes) — DONE
Audit result: the codebase is already Linux-portable.
- `_notify_macos()` / osascript: not present in the repo (no action).
- Core scripts (auto_ingest, daily_digest, weekly_review): no unguarded Mac-isms.
- `WHISPER_MODEL` Metal path in social_downloader.py is guarded by
  `Path(...).exists()` -> on Linux it skips cleanly to CPU whisper.
- `transcribe()` already falls back whisper-cli(Metal) -> faster-whisper(CPU)
  -> openai-whisper(CPU). Linux uses faster-whisper CPU.
- Added `requirements-vps.txt` (faster-whisper + playwright) so the VPS CPU
  transcription path is reproducible; base requirements.txt stays lean.
- OPEN per-board decision: which integrations (your per-project integrations) run on
  the VPS vs stay Mac-only — defer to Phase 2 config scoping.

### Phase 1 — Base VPS + vault + feed fetcher (NOT the ingest worker)
With ingest now agentic (Phase 2), Phase 1 is just the substrate:
- System deps: `python3-venv`, `ffmpeg`, `git`.
- Clone repo, venv, `pip install -r requirements.txt -r requirements-vps.txt`.
- If using browser video capture: `python -m playwright install --with-deps chromium`.
- `~/.secondbrain.env` (chmod 600).
- Place the vault on the VPS; **author `SCHEMA.md`** describing the existing
  layout so the agent (Phase 2) respects entities/concepts/sources/synthesis/
  episodic/projects.
- Thin feed fetcher only: `secondbrain-digest.timer` -> daily 06:00 runs
  daily_digest.py to drop GitHub/HN/model news into raw/generated/. The AGENT
  ingests it in Phase 2. (No ingest/weekly timers — Hermes owns those.)

### Phase 2 — Hermes = ingest + query + lint worker (THE CORE)
This is the point of the migration: Hermes does ALL the work (fully agentic)
and is queryable any time from Discord.
Official install (confirmed from repo, Linux/Python 3.11, "runs on a $5 VPS"):
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```
- Clean install via the script (NOT a copy of the Mac's 1.5 GB ~/.hermes /
  746 MB state.db). Docker is an alternative — repo ships `Dockerfile` +
  `docker-compose.yml`; containerizing gives clean isolation + easy teardown,
  worth considering for the VPS.
- Bring over ONLY: the secondbrain-agent profile (and any other project profiles you maintain),
  scoped `config.yaml` (with allow_all_users already false), `SOUL.md`, `.env`
  (only the keys those boards need — incl DISCORD_BOT_TOKEN / DISCORD_WIKI_*).
- **Repoint** `secondbrain-agent` `obsidian-graph` MCP from
  `<your-mac-vault-path>/obsidian_mcp.py` to the VPS vault path.
- Fresh `kanban.db`; init the four boards.
- Daemonize:
  - `hermes gateway run` (or `hermes gateway install` as a service) — Discord
    bot online. Bind/secure; allow_all_users=false enforced.
  - built-in cron scheduler — processes scheduled board tasks.
- **Pair yourself**: DM the bot from Discord (iPhone or Mac) -> `hermes pairing
  approve <code>` on the VPS. Verify a stranger cannot query.
- **Agentic ingest loop** (the worker): watcher (inotifywait on Linux) -> creates
  a `secondbrain` kanban task on new raw/ file -> Hermes dispatches
  secondbrain-agent -> agent runs llm-wiki ingest (orient, check existing,
  write+crosslink, update index/log). Plus a Hermes cron heartbeat for missed
  files + periodic lint (llm-wiki lint replaces weekly_review.py).
- Set `WIKI_PATH` for the skill; confirm obsidian MCP repointed to VPS vault.
- Throttle agent concurrency (8 GB box) so ingest + whisper don't OOM.
- Smoke tests (success criteria for the whole project):
  1. Drop a file in raw/ -> agent ingests it into the wiki agentically.
  2. From Discord, ask "what's in my wiki about X" -> agent answers from vault.

Note: "$5 VPS" is the idle/light-use claim. Concurrent multi-board agent runs +
CPU whisper still need real headroom — see RAM budget risk above.

### Phase 3 — Syncthing (visual layer, optional/bonus)
- Install Syncthing on VPS + Mac. Share `~/SecondBrain` (VPS) <-> Mac vault.
- Ignore patterns: `outputs/*.log`, `.last_ingest_run`. VPS is source of truth
  on first sync.
- iPhone Obsidian: SKIP Syncthing on iOS (crippled). Querying from iPhone is
  handled by Discord (Phase 2), so mobile Obsidian is unnecessary. If visual
  mobile browsing is ever wanted, use Obsidian's own Sync (paid), not Syncthing.

### Phase 4 — Cutover + verification
- Run both Mac and VPS in parallel for a few days.
- Confirm VPS ingest writes wiki, Syncthing reflects on Mac, Hermes boards
  process tasks.
- Then disable the Mac launchd timers (keep Mac as reader only).

## Security notes
- Secrets in `~/.secondbrain.env` and Hermes `.env`, chmod 600, never in git.
- Hermes dashboard / gateway: bind localhost, access via SSH tunnel or
  authenticated reverse proxy. No open ports for agent control surfaces.
- Rotate any key that has ever been pasted into a chat/transcript.

## Open questions for the operator
1. VPS RAM / vCPU / OS?
2. SSH-access setup vs generate-scripts-you-run?
3. Which boards truly need to be always-on on day one vs added in a later phase?
4. Do any optional project agents need their integrations live
   on the VPS, or run those Mac-side for now?
