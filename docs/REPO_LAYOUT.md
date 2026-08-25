# Repository layout

Annotated map of what lives where. Use this when navigating the codebase.

```
second-brain-ai/
│
├── README.md                              ← Project overview (the billboard)
├── LICENSE                                ← MIT
├── CONTRIBUTING.md                        ← How to propose changes
├── requirements.txt                       ← Base Python deps (Mac + VPS)
├── requirements-vps.txt                   ← VPS-only deps (whisper, yt-dlp, playwright)
├── setup.sh                               ← One-command vault scaffold
│
├── auto_ingest.py                         ← Deterministic fallback ingest script.
│                                            The agentic path (watcher → kanban →
│                                            llm-wiki skill) is the primary worker.
│                                            Kept as a reference / emergency tool.
├── brain_server.py                        ← Optional local HTTP server for the
│                                            browser bookmarklet capture path.
├── social_downloader.py                   ← Legacy Mac-side video clipper
│                                            (predecessor to scripts/brain_clip.py).
├── obsidian_mcp.py                        ← Graph-read MCP server that the agent
│                                            calls for backlinks / outlinks / search /
│                                            find-path / hub-detection / vault stats.
│
├── scripts/
│   ├── clip.py                            ← VPS-side clipper (yt-dlp + whisper +
│   │                                        captions, proxy-aware).
│   ├── brain_clip.py                      ← Mac-side clipper (uses local Metal
│   │                                        whisper-cli when available).
│   ├── daily_digest.py                    ← Pulls GitHub trending / HN / model
│   │                                        news into raw/generated/ at 06:00 UTC.
│   ├── file_watcher.sh                    ← Legacy macOS fswatch driver.
│   └── weekly_review.py                   ← Heartbeat-driven lint script.
│
├── deploy/
│   ├── vps/                               ← VPS deployment artifacts
│   │   ├── README.md                      ← FULL VPS RUNBOOK (the deployment guide)
│   │   ├── SCHEMA.template.md             ← Machine-readable knowledge schema
│   │   │                                    (synced to <VAULT>/wiki/SCHEMA.md
│   │   │                                    on the live box).
│   │   ├── clip.py                        ← Synced from <VAULT>/scripts/
│   │   ├── clip_yt.py                     ← YouTube-only caption clipper
│   │   ├── clip_yt_channel.py             ← Same, but every video on a channel
│   │   │                                    or playlist. Skips IDs already in
│   │   │                                    raw/, so re-runs are incremental.
│   │   ├── sb_watcher.sh                  ← inotify watcher script
│   │   ├── secondbrain-watcher.service    ← systemd unit (raw/ inotify)
│   │   ├── secondbrain-dispatch.service   ← systemd unit (standalone kanban
│   │   │                                    daemon — superseded by gateway-
│   │   │                                    embedded dispatch in production).
│   │   ├── secondbrain-heartbeat.service  ← systemd unit (daily sweep + lint)
│   │   ├── secondbrain-heartbeat.timer    ← timer that fires the heartbeat
│   │   └── hermes-gateway.override.conf.example
│   │                                      ← Drop-in that loads the profile
│   │                                        .env into the gateway service.
│   │
│   └── mac/                               ← Mac capture bridge
│       ├── README.md                      ← Mac-side setup steps
│       ├── mac_push_watcher.sh            ← fswatch → SCP to VPS
│       └── com.secondbrain.macpush.plist  ← launchd unit
│
├── docs/
│   ├── ARCHITECTURE.md                    ← The four layers, agent loop, services
│   ├── KNOWLEDGE_MODEL.md                 ← Bi-temporal facts, contradictions, ADRs
│   ├── SECURITY.md                        ← Secrets model, gateway lockdown
│   ├── DESIGN.md                          ← Intentionally-not-included choices
│   ├── REPO_LAYOUT.md                     ← This file
│   ├── VPS_DEPLOYMENT.md                  ← Long-form deployment notes
│   └── diagrams/
│       └── architecture.html              ← Single-file architecture diagram
│
├── launchd/                               ← Reference plists (older Mac-driven
│                                            layout, before the VPS migration).
│
├── vault-template/                        ← Starter vault structure
│   ├── AGENTS.md                          ← Human-facing schema companion
│   ├── SCHEMA.md                          ← Initial agent-facing schema
│   └── ...                                ← Empty folders for entities/, concepts/,
│                                            sources/, synthesis/, decisions/, etc.
│
├── .githooks/
│   └── pre-commit                         ← Scans diffs for API keys before commit.
│                                            Enable with:
│                                              git config core.hooksPath .githooks
│
├── .gitignore                             ← Blocks .env, *.env, .frag, *.bak.*,
│                                            /wiki/, /raw/, /outputs/
└── graphify-out/                          ← Auto-generated AST graph
                                             (not checked in; rebuilt on demand)
```

## Reading order for new contributors

If you're new to the codebase, read in this order:

1. [`README.md`](../README.md) — pitch + quick start
2. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — how the layers fit
3. [`deploy/vps/README.md`](../deploy/vps/README.md) — full deployment walkthrough
4. [`docs/KNOWLEDGE_MODEL.md`](KNOWLEDGE_MODEL.md) — what the agent writes
5. [`docs/SECURITY.md`](SECURITY.md) — secrets model before you fork
6. [`docs/diagrams/architecture.html`](diagrams/architecture.html) — visual overview
7. [`obsidian_mcp.py`](../obsidian_mcp.py) — read the actual MCP tool surface
8. [`scripts/clip.py`](../scripts/clip.py) — read the deterministic clipping logic

## Where to make changes

| Change | File(s) |
|--------|---------|
| Add a new capture source (e.g. Reddit) | New script in `scripts/`, update README capture table + `docs/ARCHITECTURE.md` |
| Change the knowledge model | `deploy/vps/SCHEMA.template.md`, sync to VPS vault, update `docs/KNOWLEDGE_MODEL.md` |
| Change agent behavior | The profile's `SOUL.md` on the VPS (NOT in git — see `docs/SECURITY.md`) |
| Add a new MCP tool | New `*_mcp.py` file, register in the Hermes profile config |
| Change systemd units | `deploy/vps/*.service` (then re-install on the VPS) |
| Change the Mac bridge | `deploy/mac/*` (then re-install on the Mac) |
| Update docs | `docs/*.md`, `README.md` for billboard-level changes only |
