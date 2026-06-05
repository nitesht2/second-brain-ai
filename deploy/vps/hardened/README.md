# Hardened units — confine the Second Brain agent on the VPS

The shipped `../secondbrain-*.service` units and the Hermes gateway run **as root
with no sandboxing**. The brain ingests **untrusted external content** (web pages,
YouTube/TikTok transcripts, PDFs, Instagram captions) and feeds it to an LLM agent
that runs shell tools with `--yolo`. That is a prompt-injection → root-code-exec
path whose blast radius is the **entire box**: every sibling profile
(`quadstar`/`finance`/`trading`) and its API keys, the GitHub write deploy key
(`/root/.ssh/sb_deploy`), and the Discord token.

These drop-in replacements cut that blast radius to **the vault + the Hermes
profile, and nothing else** — without changing what the agent does.

| File | Replaces / extends | Path on VPS |
|------|--------------------|-------------|
| `secondbrain-watcher.service` | `../secondbrain-watcher.service` | `/etc/systemd/system/` |
| `secondbrain-heartbeat.service` | `../secondbrain-heartbeat.service` | `/etc/systemd/system/` |
| `secondbrain-dispatch.service` | `../secondbrain-dispatch.service` (deprecated; keep disabled) | `/etc/systemd/system/` |
| `hermes-gateway-hardening.override.conf.example` | NEW drop-in next to the env `override.conf` | `~/.config/systemd/user/hermes-gateway-secondbrain-agent.service.d/hardening.conf` |

## Two layers (you asked for both)

- **Option 2 — confine in place (in these files, safe to apply now).** Keeps euid=root
  but drops *all* root capabilities (`CapabilityBoundingSet=`), forbids privilege
  escalation (`NoNewPrivileges=`), and makes the whole filesystem read-only except
  `/root/SecondBrain` + `/root/.hermes` (`ProtectSystem=strict` + `ReadWritePaths=`).
  A de-capped, filesystem-confined root process can't do most of what "root" implies.
- **Option 1 — non-root user (`User=secondbrain`, commented out).** The biggest single
  win, but a **migration, not a toggle**. Checklist at the bottom. Do it deliberately,
  later. Option 2 already gets ~80% of the benefit at ~0 migration risk.

## Apply order (low-risk → high-stakes)

**1. The ingest path first** (non-interactive, easy to watch — prove the directive
set is safe on this box before touching the bot you talk to):

```bash
cd deploy/vps/hardened
cp secondbrain-watcher.service secondbrain-heartbeat.service secondbrain-dispatch.service /etc/systemd/system/
systemctl daemon-reload
systemctl restart secondbrain-watcher
# verify the sandbox took:
systemctl show secondbrain-watcher -p ProtectSystem -p ReadWritePaths -p CapabilityBoundingSet -p NoNewPrivileges
# functional smoke test: drop a file in raw/, confirm a wiki page appears + it moves to raw/processed/
echo "# hardening smoke test $(date)" > /root/SecondBrain/raw/_hardening_test.md
journalctl -u secondbrain-watcher -f      # watch for EROFS / "Read-only file system" / permission denied
```

If ingest still works and the journal is clean over a day, the set is safe here.

**2. Then the gateway** (the always-on Discord agent — highest value, highest stakes).
Full install/verify/rollback is in the header of
`hermes-gateway-hardening.override.conf.example`. Short version:

```bash
mkdir -p ~/.config/systemd/user/hermes-gateway-secondbrain-agent.service.d
cp hermes-gateway-hardening.override.conf.example \
   ~/.config/systemd/user/hermes-gateway-secondbrain-agent.service.d/hardening.conf
systemctl --user daemon-reload && systemctl --user restart hermes-gateway-secondbrain-agent
journalctl --user -u hermes-gateway-secondbrain-agent -f   # then DM the bot a question
```

**3. (Later) the non-root migration** — checklist below.

## Rollback (both layers are instant)

```bash
# system units: restore the originals from ../  and reload
cp ../secondbrain-*.service /etc/systemd/system/ && systemctl daemon-reload && systemctl restart secondbrain-watcher
# gateway: just delete the drop-in
rm ~/.config/systemd/user/hermes-gateway-secondbrain-agent.service.d/hardening.conf
systemctl --user daemon-reload && systemctl --user restart hermes-gateway-secondbrain-agent
```

## The one decision you must make: self-editing code

`ProtectSystem=strict` makes `/usr/local/lib/hermes-agent` **read-only**, which blocks
Hermes from rewriting its own installed code at runtime (the thing
`chanakya_watchdog.sh`'s ImportError self-heal exists for).

- **Recommended:** leave it blocked. Self-modifying agent code is exactly the
  capability you want gone. Upgrade Hermes the normal way (installer/apt), not by self-edit.
- **If the gateway/ingest errors with `EROFS` / "Read-only file system" / `ImportError`**
  right after applying, Hermes is self-writing under `/usr/local`. To preserve that
  (weaker isolation), append to the `ReadWritePaths=` line:
  `ReadWritePaths=/usr/local/lib/hermes-agent`.

## What's STILL exposed after option 2 (be honest)

- `/root/.hermes` is writable and **shared with sibling profiles**. A brain compromise
  can still read `quadstar`/`finance`/`trading` `.env` keys and the Discord token under
  `/root/.hermes`. **Only the non-root split (option 1), one user per project, fully
  fixes this.**
- The process is still **euid=root** (just de-capped). A kernel-level privesc could
  re-acquire capability. Non-root closes that too.
- The GitHub deploy key: if it lives under `/root/.ssh` it's outside `ReadWritePaths`
  (unreadable to a confined unit — good), but cron jobs (`vault_backup.sh`) still use it
  as root. Consider a read-only deploy key + a separate push path.

## Non-root migration checklist (option 1 — do later, deliberately)

Running as a dedicated `secondbrain` user is the real isolation. It is involved because
everything currently assumes `HOME=/root`:

1. `useradd -m -s /bin/bash secondbrain && loginctl enable-linger secondbrain`
   (linger = the user gateway survives logout, like root's does today).
2. Move the vault: `/root/SecondBrain` → `/home/secondbrain/SecondBrain` (`chown -R secondbrain:`).
3. Recreate the Hermes profile under `/home/secondbrain/.hermes`. Fix the profile's
   absolute paths: `obsidian-graph` MCP `args` (`obsidian_mcp.py`), MCP `command:` venv
   python, the profile `.env` `WIKI_PATH`, and any `dir:/root/SecondBrain` references.
4. Move the gateway to secondbrain's **user** manager (`systemctl --user` as secondbrain;
   `XDG_RUNTIME_DIR=/run/user/$(id -u secondbrain)`). Reinstall: `hermes gateway install -p secondbrain-agent`.
5. Move the root cron jobs (`chanakya_watchdog.sh`, `vault_backup.sh`,
   `run_brain_skill.sh`, `book_drip.sh`, `sb_retry_sweep.sh`) into secondbrain's crontab.
   Update the watchdog's `XDG_RUNTIME_DIR=/run/user/0` → `/run/user/<secondbrain-uid>`.
6. Move the deploy key: `/root/.ssh/sb_deploy*` → `/home/secondbrain/.ssh/`, fix
   `~/.ssh/config`.
7. In these units, uncomment `User=`/`Group=secondbrain`, set `Environment=HOME=/home/secondbrain`,
   change every `/root/SecondBrain` + `/root/.hermes` path (incl. `ReadWritePaths=`) to the
   `/home/secondbrain/...` equivalents.
8. Smoke test the full loop (drop file → wiki page; DM bot → answer) before deleting `/root` copies.

## Directive cheat-sheet

| Directive | Effect |
|---|---|
| `NoNewPrivileges=yes` | No setuid/sudo escalation, ever |
| `CapabilityBoundingSet=` (empty) | Drop ALL Linux capabilities — neuters root in place |
| `ProtectSystem=strict` | Whole FS read-only except `ReadWritePaths=` |
| `ReadWritePaths=` | The ONLY writable trees (vault + Hermes profile) |
| `ProtectProc=invisible` / `ProcSubset=pid` | Agent can't see other processes in `/proc` |
| `PrivateTmp=yes` | Private `/tmp` (vault flock unaffected) |
| `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX` | Network ok, exotic sockets blocked |
| `RestrictNamespaces=yes` | No namespace creation (remove if using chromium capture) |
| `Protect{Kernel*,Clock,Hostname,ControlGroups}` | Can't tamper kernel/clock/host/cgroups |
| `User=` (commented) | Option 1 — real isolation, needs the migration above |
