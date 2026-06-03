#!/usr/bin/env bash
# Chanakya gateway watchdog — runs from root cron, independent of Hermes.
# Self-heals process death; alerts on token death (a restart cannot fix that).
set -u
SVC=hermes-gateway-secondbrain-agent
ENVF=/root/.hermes/profiles/secondbrain-agent/.env
LOG=/root/SecondBrain/outputs/chanakya_health.log
export XDG_RUNTIME_DIR=/run/user/0

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
note() { echo "$(ts) $1" >> "$LOG"; }

TOKEN=$(grep -E '^DISCORD_BOT_TOKEN=' "$ENVF" | head -1 | cut -d= -f2-)
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' https://discord.com/api/v10/users/@me -H "Authorization: Bot $TOKEN" 2>/dev/null)
[ "$CODE" != '200' ] && note "ALERT token-invalid (HTTP $CODE) — needs fresh Discord token in $ENVF"

ACTIVE=$(systemctl --user is-active "$SVC" 2>/dev/null)
if [ "$ACTIVE" != 'active' ]; then
  note "WARN gateway state=$ACTIVE — restarting"
  systemctl --user restart "$SVC" 2>/dev/null; sleep 5
  note "INFO post-restart state=$(systemctl --user is-active "$SVC" 2>/dev/null)"
else
  M=$(date -u +%M)
  if [ "$((10#$M))" -lt 5 ]; then note "OK gateway active, token $CODE"; fi
fi
exit 0
