#!/usr/bin/env bash
# sb_outcome_check.sh — assert the pipeline PRODUCED something, not that it is alive.
#
# chanakya_watchdog.sh checks liveness: gateway up, token valid, watcher running.
# On 2026-07-27 every one of those was green while ingest had been dead 21 days,
# harvest 7, and vault_backup had been logging "pushed" without pushing. A process
# can be perfectly alive and produce nothing, so these checks look at outputs.
#
# Each check passes, fails, or skips ("nothing to do" is not a failure — a monitor
# that cries wolf on a quiet day gets ignored, which is worse than no monitor).
# Alerts go through `hermes send`, which needs only the Discord bot token and so
# still reaches you when the LLM provider is dead. Throttled to 1/hour.
set -u
export TZ=America/Los_Angeles
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin

V=/root/SecondBrain
LOG=$V/outputs/outcome_check.log
ALERTF=/root/.hermes/scripts/.sb_last_outcome_alert
HB=/usr/local/bin/hermes
SEEN=/root/.hermes/data/feeds/x_bookmarks_seen.json

DAY=86400
now=$(date +%s)
FAILS=()

ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
note(){ echo "$(ts) $1" >>"$LOG"; }
fail(){ FAILS+=("$1"); note "FAIL $1"; }
pass(){ note "ok   $1"; }
skip(){ note "skip $1"; }

# age of a file in seconds, or a huge number when it does not exist
age(){ [ -f "$1" ] && echo $(( now - $(stat -c %Y "$1") )) || echo 999999999; }

# 1. INGEST — did raw/ actually turn into wiki pages?
#    Empty queue = nothing to do, not a failure. A backlog with no wiki writes is.
pending=$(find "$V/raw" -maxdepth 1 \( -name '*.md' -o -name '*.txt' -o -name '*.pdf' \) 2>/dev/null | wc -l)
wrote=$(find "$V/wiki" -name '*.md' -mmin -1440 2>/dev/null | wc -l)
if [ "$pending" -eq 0 ]; then
  skip "ingest (queue empty, nothing to ingest)"
elif [ "$wrote" -gt 0 ]; then
  pass "ingest ($pending queued, $wrote wiki pages written in 24h)"
else
  # only alarming once the backlog has had time to drain
  oldest=$(find "$V/raw" -maxdepth 1 \( -name '*.md' -o -name '*.txt' -o -name '*.pdf' \) -mmin +1440 2>/dev/null | wc -l)
  if [ "$oldest" -gt 0 ]; then
    fail "ingest produced NOTHING in 24h while $pending file(s) wait in raw/ (check outputs/ingest_runs.log)"
  else
    skip "ingest (queue is fresh, give it time)"
  fi
fi

# 2. BACKUP — a real commit must have landed, not just a cheerful log line.
if [ -d "$V/.git" ]; then
  last_commit=$(cd "$V" && git log -1 --format=%ct 2>/dev/null || echo 0)
  if [ $(( now - last_commit )) -lt $(( DAY * 2 )) ]; then
    pass "vault backup (last commit $(( (now - last_commit) / 3600 ))h ago)"
  else
    fail "vault backup has not committed in $(( (now - last_commit) / DAY ))d (outputs/vault_backup.log)"
  fi
  if tail -3 "$V/outputs/vault_backup.log" 2>/dev/null | grep -q ALERT; then
    fail "vault backup logged an ALERT (push or commit failing)"
  fi
else
  skip "vault backup (not a git repo)"
fi

# 3. HARVEST — the timer runs twice daily, so a seen-file older than ~26h means
#    the API call is failing. An empty xurl error usually means an expired token.
seen_age=$(age "$SEEN")
if [ "$seen_age" -lt $(( DAY + 7200 )) ]; then
  pass "x harvest (seen-file $(( seen_age / 3600 ))h old)"
else
  if xurl /2/users/me >/dev/null 2>&1; then
    fail "x harvest stale ($(( seen_age / DAY ))d) though auth is OK — check x-harvest.service"
  else
    fail "x harvest stale ($(( seen_age / DAY ))d) and xurl auth is REJECTED — token expired, re-auth (see harvest_x.py docstring)"
  fi
fi

# 4. SEMANTIC INDEX — nightly timer; a full re-embed OOM-killed the box once, and
#    the atomic writes mean a failure leaves the OLD index silently in place.
idx_age=$(age "$V/.semantic/embeddings.npy")
if [ "$idx_age" -lt $(( DAY * 2 )) ]; then
  pass "semantic index ($(( idx_age / 3600 ))h old)"
else
  fail "semantic index stale $(( idx_age / DAY ))d (brain-semantic-reindex.service)"
fi

# 5. CAPACITY — the box is small; the reindex and clip paths are the memory hogs.
disk=$(df --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')
swap_total=$(free -m | awk '/^Swap:/{print $2}')
swap_used=$(free -m | awk '/^Swap:/{print $3}')
swap_pct=0
[ "${swap_total:-0}" -gt 0 ] && swap_pct=$(( swap_used * 100 / swap_total ))
[ "${disk:-0}" -ge 85 ] && fail "disk ${disk}% full" || pass "disk ${disk}%"
[ "$swap_pct" -ge 90 ] && fail "swap ${swap_pct}% used" || pass "swap ${swap_pct}%"

# ── report ─────────────────────────────────────────────────────────────────
if [ ${#FAILS[@]} -eq 0 ]; then
  note "ALL OK"
  exit 0
fi

msg="⚠️ Second Brain outcome check — ${#FAILS[@]} problem(s):"
for f in "${FAILS[@]}"; do msg="$msg"$'\n'"• $f"; done
note "ALERTING: ${#FAILS[@]} failure(s)"

last=$(cat "$ALERTF" 2>/dev/null || echo 0)
if [ $(( now - last )) -ge 3600 ]; then
  # `hermes send` only needs the bot token, so this still delivers when inference is down
  echo "$msg" | "$HB" -p secondbrain-agent send -t discord -q 2>>"$LOG" && echo "$now" >"$ALERTF"
else
  note "(alert throttled, last sent $(( (now - last) / 60 ))m ago)"
fi
exit 1
