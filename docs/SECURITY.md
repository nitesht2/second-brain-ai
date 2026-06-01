# Security model

This system holds API keys (LLM, X, Discord bot, optional proxy) and runs an
always-on bot that can act on your behalf in Discord. The security boundary is
deliberate.

## Separation of code and secrets

The single most important rule: **code goes in git, secrets stay on the server.**

| What | Where | In git? |
|------|-------|---------|
| Code, templates, unit files | This repo | ✅ yes |
| Architecture diagrams, runbooks | `docs/`, `deploy/` | ✅ yes |
| LLM API key, Discord bot token, channel IDs, proxy URL | `~/.hermes/profiles/<profile>/.env` (`chmod 600`) | ❌ never |
| X API credentials | `~/.xurl` (managed by `xurl` CLI, `chmod 600`) | ❌ never |
| The vault itself (your notes) | `~/SecondBrain/wiki/`, `raw/` | ❌ never (`.gitignore` blocks it) |

If you fork: place your secrets in the gitignored `.env`/`.xurl` files. Do not
edit the systemd units or scripts to hardcode credentials. The drop-in pattern
(`EnvironmentFile=`) is what feeds the values into the running process.

## `.gitignore` enforcement

The repo's `.gitignore` blocks:

```
.env
*.env
.secondbrain.env
.frag
*.bak.*
/wiki/
/raw/
/outputs/
```

Plus a pre-commit hook in `.githooks/pre-commit` that scans staged diffs for
OpenAI/Anthropic-style keys and `*_API_KEY=` patterns. Enable it with:

```bash
git config core.hooksPath .githooks
```

## Bot lockdown

The Discord gateway defaults to **deny**:

```yaml
gateway:
  allow_all_users: false
```

Plus a top-level `GATEWAY_ALLOW_ALL_USERS: false` in the main `config.yaml` for
defense in depth.

Authorized users go in the profile `.env`:

```bash
DISCORD_ALLOWED_USERS=<your-discord-user-id>
```

Anyone else who DMs the bot gets refused at the gateway level. There is no
auto-approval — even pairing codes are off by default. This means a Discord
account compromise of a *different* user can't drive your agent.

## Verifying repo cleanliness

To confirm no secrets ever made it into this repo's history:

```bash
git grep -nIE "sk-[A-Za-z0-9]{20,}|API_KEY\s*=\s*['\"][A-Za-z0-9]" $(git rev-list --all)
```

Should return nothing. If you're forking, run the same check on your fork
periodically — especially after any commit that touches `.env.template` or
deploy scripts.

## What the bot can and can't do

Once authorized, the bot can:

- Read any tweet, profile, bookmark you have access to (via xurl + your X creds)
- Read any URL (via `web_extract`)
- Search the web (via `duckduckgo-search`)
- Download video/audio (via `yt-dlp` + your proxy if configured)
- Write into your vault
- Reply on Discord

The bot **cannot**:

- Post to X (xurl bearer + OAuth1 setup intentionally skips write scopes; add
  them only if you want posting)
- Spend money it doesn't have a key for
- Execute arbitrary code outside the agent runtime sandbox

## Key rotation

When you suspect a credential has been exposed (e.g. pasted into a chat, leaked
in a screenshot):

1. Rotate the key in the provider dashboard (OpenRouter, DeepSeek, X dev portal,
   your proxy provider, Discord developer portal).
2. Update the corresponding entry in `~/.hermes/profiles/<profile>/.env`.
3. For X: re-run `xurl auth app --bearer-token <new>` (or OAuth1/OAuth2 commands
   for the modes you use).
4. Restart the gateway: `systemctl --user restart hermes-gateway-<profile>`.
5. Verify with a quick health check.

This is cheap; do it on any suspicion, not just confirmed leaks.

## Threat model — what's NOT defended

Be honest about the boundaries:

- **VPS compromise** — if an attacker gets shell on your VPS, they have all the
  secrets. Standard server hygiene (key-only SSH, fail2ban, unattended-upgrades,
  no public ports beyond SSH) is on you, not the agent.
- **Supply chain** — Hermes, yt-dlp, faster-whisper, xurl all run with full
  filesystem access in the agent's user. A malicious update from any of those
  upstreams could exfiltrate the `.env`. Pin versions if this matters to you.
- **Multi-user** — the system assumes a single human owner. No tenant isolation.
- **Discord platform** — anyone who can compromise the bot's own Discord
  application can hijack it. Use 2FA on the developer account.

For a personal knowledge base, the trade-off is acceptable. For team or
multi-user use, additional hardening would be needed.
