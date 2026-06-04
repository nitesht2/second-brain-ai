#!/usr/bin/env bash
# Chanakya watchdog — runs every 5 min from root cron, independent of Hermes.
# Self-heals gateway; ALERTS to Discord (throttled 1/hr) on token death,
# kanban corruption, or a stalled ingest queue.
set -u
export TZ=America/Los_Angeles
SVC=hermes-gateway-secondbrain-agent
ENVF=/root/.hermes/profiles/secondbrain-agent/.env
LOG=/root/SecondBrain/outputs/chanakya_health.log
BOARD=secondbrain
STALLF=/root/.hermes/scripts/.sb_stall_count
ALERTF=/root/.hermes/scripts/.sb_last_alert
HB=/usr/local/bin/hermes
export XDG_RUNTIME_DIR=/run/user/0
ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
note(){ echo "$(ts) $1" >> "$LOG"; }
# Discord alert, throttled to once per hour
alert(){
  note "ALERT $1"
  local now last; now=$(date +%s); last=$(cat "$ALERTF" 2>/dev/null || echo 0)
  if [ $((now - last)) -ge 3600 ]; then
    echo "⚠️ Second Brain watchdog: $1" | "$HB" -p secondbrain-agent send -t discord -q 2>>"$LOG" && echo "$now" > "$ALERTF"
  fi
}

# 1. Discord token valid?
TOKEN=$(grep -E '^DISCORD_BOT_TOKEN=' "$ENVF" | head -1 | cut -d= -f2-)
CODE=$(curl -sS -m 10 -o /dev/null -w '%{http_code}' https://discord.com/api/v10/users/@me -H "Authorization: Bot $TOKEN" 2>/dev/null)
[ "$CODE" != '200' ] && alert "Discord token invalid (HTTP $CODE) — needs a fresh token in profile .env"

# 2. Gateway alive?
ACTIVE=$(systemctl --user is-active "$SVC" 2>/dev/null)
if [ "$ACTIVE" != 'active' ]; then
  note "WARN gateway state=$ACTIVE — restarting"; systemctl --user restart "$SVC" 2>/dev/null; sleep 5
  NOW=$(systemctl --user is-active "$SVC" 2>/dev/null); note "INFO post-restart=$NOW"
  [ "$NOW" != 'active' ] && alert "gateway down and restart failed (state=$NOW)"
fi

# 3. Kanban health (the 30h-silent-outage check)
KOUT=$("$HB" kanban --board "$BOARD" stats 2>&1)
if echo "$KOUT" | grep -qiE 'corrupt|integrity_check'; then
  alert "kanban DB corrupt — ingest pipeline stalled. Rebuild: rm boards/$BOARD/kanban.db* then 'hermes kanban list'"
else
  # stall: ready tasks present but nothing running, persisting across checks
  READY=$(echo "$KOUT" | awk '/ready/{print $2; exit}'); RUN=$(echo "$KOUT" | awk '/running/{print $2; exit}')
  READY=${READY:-0}; RUN=${RUN:-0}
  if [ "$READY" -gt 0 ] 2>/dev/null && [ "$RUN" -eq 0 ] 2>/dev/null; then
    C=$(( $(cat "$STALLF" 2>/dev/null || echo 0) + 1 )); echo "$C" > "$STALLF"
    [ "$C" -ge 3 ] && alert "ingest queue stalled — $READY tasks ready, 0 running for ~15min. Check the gateway dispatcher."
  else
    echo 0 > "$STALLF"
  fi
fi

# hourly OK heartbeat
M=$(date -u +%M); [ "$((10#$M))" -lt 5 ] && note "OK gw=$ACTIVE token=$CODE kanban_ready=${READY:-?}"
exit 0
