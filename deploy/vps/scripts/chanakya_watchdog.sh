#!/usr/bin/env bash
# Chanakya watchdog — every 5 min from root cron, independent of Hermes.
# Self-heals gateway + stalled ingest; alerts to Discord (throttled 1/hr).
# Kanban-free: the brain's ingest is sb_ingest.sh (flock), raw/ is the queue.
set -u
export TZ=America/Los_Angeles
SVC=hermes-gateway-secondbrain-agent
VAULT=/root/SecondBrain
ENVF=/root/.hermes/profiles/secondbrain-agent/.env
LOG=$VAULT/outputs/chanakya_health.log
ALERTF=/root/.hermes/scripts/.sb_last_alert
HB=/usr/local/bin/hermes
export XDG_RUNTIME_DIR=/run/user/0
ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
note(){ echo "$(ts) $1" >>"$LOG"; }
alert(){ note "ALERT $1"; local now last; now=$(date +%s); last=$(cat "$ALERTF" 2>/dev/null||echo 0)
  if [ $((now-last)) -ge 3600 ]; then echo "⚠️ Second Brain watchdog: $1" | "$HB" -p secondbrain-agent send -t discord -q 2>>"$LOG" && echo "$now" >"$ALERTF"; fi; }

# 1. Discord token valid?
TOKEN=$(grep -E '^DISCORD_BOT_TOKEN=' "$ENVF"|head -1|cut -d= -f2-)
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' https://discord.com/api/v10/users/@me -H "Authorization: Bot $TOKEN" 2>/dev/null)
[ "$CODE" != '200' ] && alert "Discord token invalid (HTTP $CODE) — needs fresh token in profile .env"

# 2. Gateway alive?
ACTIVE=$(systemctl --user is-active "$SVC" 2>/dev/null)
if [ "$ACTIVE" != 'active' ]; then
  note "WARN gateway=$ACTIVE — restarting"; systemctl --user restart "$SVC" 2>/dev/null; sleep 5
  NOW=$(systemctl --user is-active "$SVC" 2>/dev/null); note "INFO post-restart=$NOW"
  [ "$NOW" != 'active' ] && alert "gateway down, restart failed (=$NOW)"
fi

# 3. Ingest stalled? (files stuck in raw/ >20min and nothing ingesting) -> kick sweep + alert
STUCK=$(find "$VAULT/raw" -maxdepth 1 -name '*.md' -mmin +20 2>/dev/null | wc -l)
ING=$(pgrep -f 'scripts/sb_ingest.sh' 2>/dev/null | wc -l)
if [ "$STUCK" -gt 0 ] && [ "$ING" -eq 0 ]; then
  /root/SecondBrain/scripts/sb_retry_sweep.sh >/dev/null 2>&1 &
  alert "ingest stalled: $STUCK file(s) stuck in raw/ >20min — kicked retry sweep"
fi


# 4. Stale-code / ImportError self-heal (Hermes edits its own core while running ->
#    gateway serves a stale in-memory module -> ImportError on every message until restart)
IMPERR=$(journalctl --user -u "$SVC" --since '6 min ago' 2>/dev/null | grep -ciE 'ImportError|cannot import name')
if [ "$IMPERR" -gt 0 ]; then
  LR=/root/.hermes/scripts/.sb_last_imprestart; last=$(cat "$LR" 2>/dev/null||echo 0); now=$(date +%s)
  if [ $((now-last)) -ge 600 ]; then
    note "ImportError x$IMPERR — restarting gateway to reload code"
    systemctl --user restart "$SVC"; echo "$now" >"$LR"
    alert "gateway hit ImportError (stale code after a Hermes self-edit) — auto-restarted to reload"
  fi
fi

# hourly heartbeat
M=$(date -u +%M); [ "$((10#$M))" -lt 5 ] && note "OK gw=$ACTIVE token=$CODE raw_stuck=$STUCK"
exit 0
