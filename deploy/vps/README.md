# VPS Deployment — Fully Agentic Second Brain (Hermes)

Runbook for the always-on, agentic Second Brain on a Linux VPS. Hermes'
`secondbrain-agent` (with the `llm-wiki` skill) is the worker: it ingests
`raw/` files into the wiki and answers queries — no `auto_ingest.py` on the
agentic path. Verified on a small KVM VPS (2 vCPU, 8 GB, Ubuntu 24.04) with
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
| `skills/*/SKILL.md` | `/root/.hermes/profiles/secondbrain-agent/skills/` | the 4 scheduled synthesis skills |
| `scripts/run_brain_skill.sh` | `/root/.hermes/scripts/` | Pacific/DST-safe skill runner + Discord delivery |
| `scripts/chanakya_watchdog.sh` | `/root/.hermes/scripts/` | 5-min gateway/token health check + auto-restart |
| `scripts/vault_backup.sh` | `/root/.hermes/scripts/` | daily vault commit + push to GitHub |
| `scripts/doc2md.py` | `<vault>/scripts/` | convert a document (PDF/Word/PPT/Excel/image) → Markdown into `raw/` |

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

## Discord query layer (the bot)

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

### Make replies copy-paste friendly

Hermes' `~/.hermes/config.yaml` has three knobs that decide when a reply gets sent as a single Discord attachment (non-selectable) vs as inline text messages (per-message selectable). Defaults are aggressive — most useful replies trip them and end up as attachments.

In `~/.hermes/config.yaml`:

```yaml
paste_collapse_threshold: 40            # was 5  (lines)
paste_collapse_threshold_fallback: 40   # was 5
paste_collapse_char_threshold: 6000     # was 2000 (chars)
```

These raise the bar enough that normal Q&A answers stay inline (and selectable for partial copy). Discord still splits messages over 2000 chars into multiple posts automatically — each post is independently selectable. Genuinely long responses (>40 lines OR >6000 chars) still attach.

Restart the gateway after editing:

```bash
systemctl --user restart hermes-gateway-<your-profile>
```

### Discord gotchas (cost real debugging time)
- **Slash-command cap (error 30032):** if the bot accumulates 100 global slash
  commands, sync crashes `_run_post_connect_initialization` and **silently blocks
  message handling**. Clear them:
  `curl -X PUT -H "Authorization: Bot $TOKEN" -d '[]' https://discord.com/api/v10/applications/<APP_ID>/commands`
- Named-profile gateways don't inherit the global `~/.hermes/.env` — hence the drop-in.
- Every gateway restart posts a one-off "Gateway shutting down" notice to the channel.

## Scheduled synthesis skills (the autonomous layer)

Four Hermes skills that read the vault on a schedule and write outputs back to it.
Source lives in `deploy/vps/skills/`. Each is a directory with a single `SKILL.md`
using Hermes' standard frontmatter format (`name`, `description`).

| Skill | When (Pacific) | What it does | Output |
|---|---|---|---|
| `morning-brief` | Daily 6:00 am | Reads index + recent log + hubs via obsidian-graph MCP, generates a brief grounded in actual vault content | `outputs/briefings/<date>-morning-brief.md` |
| `connection-finder` | Sunday 10:00 am | Finds non-obvious links between this-week notes and older hubs using `find_path` / `get_graph_neighbors`. Includes orphan rescues. | `outputs/analyses/<date>-connections.md` |
| `weekly-synthesis` | Sunday 12:00 pm | Synthesizes the full week. Updates `wiki/index.md` priorities section in place. | `outputs/reviews/<date>-weekly-synthesis.md` |
| `thinking-partner` | Sunday 1:00 pm | Surfaces tensions, underdeveloped claims, missing connections, open questions. Pushes, does not summarize. | `outputs/analyses/<date>-thinking-partner.md` |

All four are graph-aware — they call the `obsidian-graph` MCP tools first
(`get_hub_notes`, `trace_concept`, `find_path`, `get_graph_neighbors`) before
falling back to raw file reads. This is what separates them from naive
"read every file" scheduled jobs.

### Install

Copy the skill directories into the profile:

```bash
rsync -av deploy/vps/skills/ /root/.hermes/profiles/secondbrain-agent/skills/
```

Skills are auto-discovered on next gateway restart. Verify with:

```bash
ls /root/.hermes/profiles/secondbrain-agent/skills/ | grep -E "morning-brief|connection-finder|thinking-partner|weekly-synthesis"
```

### Schedule (Pacific time, DST-safe)

**Do NOT use Hermes' built-in cron for these.** Hermes cron is hardwired to UTC —
the profile `timezone:` setting only changes log display, not when jobs fire, and
there's no per-job timezone flag. A fixed UTC time also drifts an hour across the
PST↔PDT switch. Instead, drive the skills from **Linux system cron with
`CRON_TZ=America/Los_Angeles`** (which IS daylight-saving aware) and deliver via
`hermes send`. This also makes the skills independent of the gateway — they run
even if the gateway is down, because `hermes send` only needs the bot token.

The driver is [`scripts/run_brain_skill.sh`](scripts/run_brain_skill.sh): it runs a
skill standalone (`hermes -p secondbrain-agent -z "..." --skill <name> --yolo`),
finds the fresh output file, and posts it to the Discord home channel
(`hermes -p secondbrain-agent send -t discord -f <file>`).

Install the driver, then add the cron block:

```bash
cp deploy/vps/scripts/run_brain_skill.sh /root/.hermes/scripts/ && chmod +x /root/.hermes/scripts/run_brain_skill.sh

crontab -e   # add the block below
```

```cron
# --- Second Brain: Pacific time, DST-aware (auto PST<->PDT) ---
CRON_TZ=America/Los_Angeles
0 6  * * *  /root/.hermes/scripts/run_brain_skill.sh morning-brief
0 10 * * 0  /root/.hermes/scripts/run_brain_skill.sh connection-finder
0 12 * * 0  /root/.hermes/scripts/run_brain_skill.sh weekly-synthesis
0 13 * * 0  /root/.hermes/scripts/run_brain_skill.sh thinking-partner
```

> `CRON_TZ` applies to every line BELOW it until changed — keep any UTC-anchored
> jobs (e.g. posting-peak crons for other projects) ABOVE this marker so they stay UTC.

If you also created Hermes-cron versions of these jobs, **pause them** so they don't
double-fire: `hermes -p secondbrain-agent cron pause morning-brief` (repeat for each).

### Notes

- The driver runs skills under `-p secondbrain-agent` so the `obsidian-graph` MCP is loaded; under the default profile they drop to degraded mode (file reads only, flagged in output).
- The driver `cd`s to `/root/SecondBrain` so skills resolve relative paths (`outputs/`, `wiki/`).
- For manual testing: `/root/.hermes/scripts/run_brain_skill.sh morning-brief` (runs + delivers), or just `secondbrain-agent -z "Run the morning-brief skill" --skill morning-brief` to run without delivery.
- Only `weekly-synthesis` mutates the vault (edits `wiki/index.md` between `<!-- PRIORITIES_START -->` / `<!-- PRIORITIES_END -->` markers, added on first run).
- First runs take 60–120s — they pull a lot of context. Subsequent runs hit DeepSeek's prompt cache. Runs log to `outputs/skill_runs.log`.

## Reliability & backup (keep it alive)

Three system-cron jobs (independent of Hermes, so they run even if the gateway is
down) keep the brain healthy and recoverable. All on Pacific time — put them under
the same `CRON_TZ=America/Los_Angeles` marker as the skills above.

```cron
*/5 * * * * /root/.hermes/scripts/chanakya_watchdog.sh
30 4 * * *  /root/.hermes/scripts/vault_backup.sh
```

### Watchdog — Chanakya never silently dies

[`scripts/chanakya_watchdog.sh`](scripts/chanakya_watchdog.sh) runs every 5 min and:
- restarts the gateway if the user service isn't `active`,
- curls the Discord `/users/@me` endpoint with the live token — if it's not `200`,
  logs an ALERT (a dead token can't be auto-fixed; it needs a fresh one in the
  profile `.env`),
- writes status to `outputs/chanakya_health.log`.

This backs up systemd's `Restart=always` — it covers the gap where systemd gives up
after a crash-loop, or where the token silently expires. Needs
`export XDG_RUNTIME_DIR=/run/user/0` to drive `systemctl --user` from root cron.

```bash
cp deploy/vps/scripts/chanakya_watchdog.sh /root/.hermes/scripts/ && chmod +x /root/.hermes/scripts/chanakya_watchdog.sh
```

### Vault backup — survive a disk failure

The vault is a git repo (`wiki/`, `outputs/`, the Python engine). Back it up off-box
daily via [`scripts/vault_backup.sh`](scripts/vault_backup.sh) (commit + push, logs to
`outputs/vault_backup.log`).

**One-time push-auth setup** (the VPS needs to push without a password):

```bash
# 1. deploy key on the VPS
ssh-keygen -t ed25519 -N '' -f /root/.ssh/sb_deploy -C 'secondbrain-vps-deploy'

# 2. add it WRITABLE to the vault repo (from a machine with gh + repo admin)
gh api -X POST repos/<you>/second-brain-vault/keys \
  -f title='secondbrain-vps-deploy' -f key="$(ssh <vps> cat /root/.ssh/sb_deploy.pub)" -F read_only=false

# 3. point github at that key + use SSH remote, on the VPS
printf 'Host github.com\n  IdentityFile /root/.ssh/sb_deploy\n  IdentitiesOnly yes\n' >> /root/.ssh/config
cd /root/SecondBrain && git remote set-url origin git@github.com:<you>/second-brain-vault.git
```

> **Gotcha:** make sure `.gitignore` excludes `.venv/`, `*.so`, and `outputs/*.log` —
> otherwise the first commit drags in 70 MB+ of Python venv binaries and GitHub warns.
> `git rm -r --cached .venv` if it already got tracked.

### tirith security scanner — must match the box architecture

The prompt-injection scanner (`tirith`) is bundled per-profile in
`profiles/<name>/bin/tirith`. If you imported the profile from an Apple-Silicon Mac
(`hermes profile export`), that binary is **arm64** and silently fails on an x86_64
VPS (`Exec format error` → scanner fail-opens = OFF). Replace it with the host-arch
build that ships in `~/.hermes/bin/`:

```bash
file /root/.hermes/profiles/secondbrain-agent/bin/tirith   # if "Mach-O arm64" → wrong
cp /root/.hermes/bin/tirith /root/.hermes/profiles/secondbrain-agent/bin/tirith
/root/.hermes/profiles/secondbrain-agent/bin/tirith --version   # should print, not error
```

## Document ingestion (PDF / Word / PowerPoint / Excel / images)

The web path (`web_extract`) handles HTML; the video path (`clip.py`) handles
media. Documents are the third lane — converted to clean, structure-preserving
Markdown with [microsoft/markitdown](https://github.com/microsoft/markitdown) via
[`scripts/doc2md.py`](scripts/doc2md.py).

```bash
/root/SecondBrain/.venv/bin/pip install 'markitdown[pdf,docx,pptx,xlsx]'
cp deploy/vps/scripts/doc2md.py /root/SecondBrain/scripts/ && chmod +x /root/SecondBrain/scripts/doc2md.py
```

Usage (the agent runs this; you can too):

```bash
/root/SecondBrain/.venv/bin/python /root/SecondBrain/scripts/doc2md.py "<file-path-or-url>"
```

It converts the doc → Markdown and drops it in `raw/` — so it flows through the
**same** watcher → ingest pipeline as everything else (dedup, cross-link, SCHEMA).
Chanakya routes documents here automatically (see `SOUL.md`): a pasted/attached
PDF or Office file → `doc2md.py`, a video URL → `clip.py`, an article → `web_extract`.

Why markitdown and not raw PDF text extraction: it preserves headings, tables, and
lists, so the ingest agent extracts entities/concepts far better than from a flat
text dump. It runs locally — no API cost. (Keep `clip.py` for video; markitdown's
own YouTube path uses the caption API that the VPS IP is blocked from.)

## Mac-free clipping via residential proxy

Datacenter IPs (your VPS) are blocked by YouTube/TikTok for scraping. A residential
proxy makes yt-dlp look like a home connection. Any provider works (e.g. DataImpulse
~$1/GB, IPRoyal, etc.) — all give an `http://user:pass@host:port` string.

1. Buy a small residential (NOT datacenter) plan, get the endpoint string.
2. Add to the profile `.env` (kept out of git):
   ```
   BRAIN_PROXY=http://USER:PASS@HOST:PORT
   ```
3. `scripts/clip.py` reads `BRAIN_PROXY` and routes yt-dlp through it. Restart the
   gateway. Then a video URL clips fully on the VPS (no Mac).

## X / Twitter search + ingest via xurl

Install: `curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash`

Simplest auth for read/search is **app-only bearer** (no browser OAuth needed):
```
xurl auth app --bearer-token YOUR_BEARER_TOKEN   # from developer.x.com (pay-as-you-go plan)
xurl search "QUERY" -n 10                          # verify
```
The X dev app/project must be on a plan that allows recent search (pay-as-you-go).
For posting *as* a user you'd instead do the OAuth2 flow (`xurl auth oauth2 --app my-app`
via an `ssh -L 8080:localhost:8080` tunnel) — not needed for ingest.

**Profile-home gotcha:** the agent runs with `HOME=<profile>/home`, so xurl's
`~/.xurl` (default `/root/.xurl`) isn't found. Symlink it:
```
ln -sf /root/.xurl /root/.hermes/profiles/secondbrain-agent/home/.xurl
```

## Gotchas learned the hard way

- `kanban daemon` is deprecated (dispatcher now lives in the gateway). The
  standalone daemon needs `--force`; it's board-scoped, which is fine until the
  gateway goes live — then drop it to avoid claim races.
- Named profiles need their own `.env`; the global one does not propagate.
- The obsidian MCP must run under the Hermes venv python (has `mcp`).
