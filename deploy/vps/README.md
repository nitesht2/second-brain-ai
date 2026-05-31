# VPS Deployment — Fully Agentic Second Brain (Hermes)

Runbook for the always-on, agentic Second Brain on a Linux VPS. Hermes'
`secondbrain-agent` (with the `llm-wiki` skill) is the worker: it ingests
`raw/` files into the wiki and answers queries — no `auto_ingest.py` on the
agentic path. Verified on Hostinger KVM 2 (2 vCPU, 8 GB, Ubuntu 24.04) with
Hermes Agent v0.14.0 already installed.

Full plan + rationale: `../../docs/VPS_DEPLOYMENT.md`.

## Files here

| File | Goes to | Purpose |
|------|---------|---------|
| `sb_watcher.sh` | `/root/SecondBrain/scripts/` | inotify on `raw/` → creates a kanban ingest task |
| `secondbrain-watcher.service` | `/etc/systemd/system/` | runs the watcher (Restart=always) |
| `secondbrain-dispatch.service` | `/etc/systemd/system/` | board-scoped kanban dispatcher (`--force`) |
| `secondbrain-heartbeat.service` | `/etc/systemd/system/` | daily sweep + lint task |
| `secondbrain-heartbeat.timer` | `/etc/systemd/system/` | fires heartbeat 04:07 daily |
| `SCHEMA.template.md` | `<vault>/wiki/SCHEMA.md` | agent-facing schema (Title Case, layout, evergreen format) |

Paths assume `HOME=/root`. Adjust if deploying as a non-root user.

## Prerequisites on the VPS

- Hermes Agent installed (`curl -fsSL .../NousResearch/hermes-agent/main/scripts/install.sh | bash`)
- `llm-wiki` skill present (ships with Hermes)
- 4 GB swap (small box OOM insurance): `fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` + fstab line
- `apt install -y inotify-tools ffmpeg`
- Provider key: `OPENROUTER_API_KEY` in `/root/.hermes/.env`

## Deploy steps

1. **Vault** — rsync the vault to `/root/SecondBrain` (wiki + raw + brand + obsidian_mcp.py).
2. **SCHEMA** — copy `SCHEMA.template.md` to `<vault>/wiki/SCHEMA.md`.
3. **Profile** — `hermes profile import secondbrain-agent.tar.gz`, then FIX:
   - obsidian-graph MCP `args` path → `/root/SecondBrain/obsidian_mcp.py`
   - MCP `command:` → `/usr/local/lib/hermes-agent/venv/bin/python3` (system python3 lacks the `mcp` pkg)
   - `model:` → OpenRouter primary (`deepseek/deepseek-chat`), drop any `localhost` ollama fallback
   - `providers: {}` (empty — lets the env key resolve)
   - create `profiles/secondbrain-agent/.env` with `OPENROUTER_API_KEY` + `WIKI_PATH`
     (named profiles do NOT inherit the global `~/.hermes/.env`)
4. **Security** — set `gateway.allow_all_users: false` in `/root/.hermes/config.yaml`.
5. **Board** — `hermes kanban boards create secondbrain --name "Second Brain"`,
   then `hermes kanban boards set-default-workdir secondbrain /root/SecondBrain`.
6. **Services** —
   ```bash
   cp sb_watcher.sh /root/SecondBrain/scripts/ && chmod +x /root/SecondBrain/scripts/sb_watcher.sh
   cp secondbrain-*.service secondbrain-*.timer /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now secondbrain-watcher secondbrain-dispatch secondbrain-heartbeat.timer
   ```
7. **Verify** — drop a file in `raw/`; within ~60 s a wiki page appears and the
   raw file moves to `raw/processed/`.

## Discord query layer (DONE — "Chanakya" bot, live & verified)

Two-way plain-English chat from phone/desktop, powered by Hermes + DeepSeek flash.
Per-profile gateway runs as a systemd **user** service (linger enabled → survives logout).

Setup (all in the secondbrain-agent PROFILE, not global):
1. Put the bot token + channel in `profiles/secondbrain-agent/.env`:
   `DISCORD_BOT_TOKEN=...`, `DISCORD_HOME_CHANNEL=<channel id>`,
   `DISCORD_ALLOWED_USERS=<your discord user id>` (gateway is locked;
   allow_all_users=false denies everyone else, no auto-pairing).
2. Enable the platform in `profiles/secondbrain-agent/config.yaml`:
   ```yaml
   platforms:
     discord:
       enabled: true
   ```
   and in the `discord:` block set `require_mention: false` (frictionless chat)
   and `auto_thread: false` (replies inline, not in threads).
3. Install + run the gateway:
   `hermes gateway install -p secondbrain-agent` then `hermes gateway start -p secondbrain-agent`.
4. **Force the profile .env into the service** via a drop-in (the generated unit
   has no EnvironmentFile and Hermes rewrites the unit on restart):
   copy `hermes-gateway.override.conf.example` to
   `~/.config/systemd/user/hermes-gateway-secondbrain-agent.service.d/override.conf`,
   then `systemctl --user daemon-reload && systemctl --user restart hermes-gateway-secondbrain-agent`.
5. **Stop the standalone dispatcher** — the gateway embeds one; running both
   races for kanban claims: `systemctl stop secondbrain-dispatch` (or leave it
   if you keep ingest dispatch board-scoped and gateway only for chat — but the
   gateway dispatches too, so prefer stopping the standalone).

### Discord gotchas (cost real debugging time)
- **Slash-command cap (error 30032):** if the bot accumulates 100 global slash
  commands, sync crashes `_run_post_connect_initialization` and **silently blocks
  message handling**. Clear them:
  `curl -X PUT -H "Authorization: Bot $TOKEN" -d '[]' https://discord.com/api/v10/applications/<APP_ID>/commands`
- Named-profile gateways don't inherit the global `~/.hermes/.env` — hence the drop-in.
- Every gateway restart posts a one-off "Gateway shutting down" notice to the channel.

## Gotchas learned the hard way

- `kanban daemon` is deprecated (dispatcher now lives in the gateway). The
  standalone daemon needs `--force`; it's board-scoped, which is fine until the
  gateway goes live — then drop it to avoid claim races.
- Named profiles need their own `.env`; the global one does not propagate.
- The obsidian MCP must run under the Hermes venv python (has `mcp`).
