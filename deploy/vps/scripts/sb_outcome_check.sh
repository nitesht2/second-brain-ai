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
# still reaches you when the LLM provider is dead. Problems are throttled to
# 1/hour; a healthy day still reports once, because a monitor that only speaks
# when broken cannot be distinguished from a monitor that has itself died.
set -u
export TZ=America/Los_Angeles
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin

V=/root/SecondBrain
LOG=$V/outputs/outcome_check.log
ALERTF=/root/.hermes/scripts/.sb_last_outcome_alert
DAILYF=/root/.hermes/scripts/.sb_last_outcome_daily
HB=/usr/local/bin/hermes
SEEN=/root/.hermes/data/feeds/x_bookmarks_seen.json

DAY=86400
now=$(date +%s)
FAILS=()
# Healthy days used to report to a logfile nobody opens, so a working pipeline and
# a dead one looked identical from Discord. That is the exact failure this script
# exists to catch, so the passes are collected and sent too.
OKS=()

ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
note(){ echo "$(ts) $1" >>"$LOG"; }
fail(){ FAILS+=("$1"); note "FAIL $1"; }
pass(){ OKS+=("$1"); note "ok   $1"; }
skip(){ OKS+=("$1"); note "skip $1"; }

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
  # An ALERT older than the last successful push is history, not a fault. A flat
  # `tail -3 | grep ALERT` keeps firing for every run it takes the resolved alert
  # to scroll out of the window, which is how a monitor teaches you to ignore it.
  # Read newest-first and stop at the last "pushed": only what is above it counts.
  # `sed -n '/pushed /q;p'`, not a `1,/pushed /p` range — a range never matches its
  # end pattern on line 1, so a log whose newest line is the push prints to EOF.
  if tail -40 "$V/outputs/vault_backup.log" 2>/dev/null \
       | tac | sed -n '/pushed /q;p' | grep -q ALERT; then
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

# ── the number that tracks the vault's actual problem ──────────────────────
# Not a pass/fail. Pages accumulate on their own; decisions only move when you
# answer one. A rising open count with a flat answered count is the vault turning
# back into an archive, and no liveness check can see that.
dec_open=$(grep -l '^status: open' "$V"/wiki/decisions/*.md 2>/dev/null | wc -l)
dec_ans=$(grep -l '^status: answered' "$V"/wiki/decisions/*.md 2>/dev/null | wc -l)

# `hermes send` only needs the Discord bot token, so both paths below still
# deliver when the LLM provider is dead — which is when you most need to hear it.
send(){ echo "$1" | "$HB" -p secondbrain-agent send -t discord -q 2>>"$LOG"; }

# ── report: healthy ────────────────────────────────────────────────────────
if [ ${#FAILS[@]} -eq 0 ]; then
  note "ALL OK"
  # Once per day. The timer is daily, but a manual run should not double-post.
  last_ok=$(cat "$DAILYF" 2>/dev/null || echo 0)
  if [ $(( now - last_ok )) -lt $(( DAY - 3600 )) ]; then
    note "(daily report already sent $(( (now - last_ok) / 3600 ))h ago)"
    exit 0
  fi
  msg="✅ Second Brain — all ${#OKS[@]} checks passed"
  for o in "${OKS[@]}"; do msg="$msg"$'\n'"• $o"; done
  msg="$msg"$'\n'"• decisions: $dec_open open, $dec_ans answered"
  send "$msg" && echo "$now" >"$DAILYF"
  exit 0
fi

# ── report: problems ───────────────────────────────────────────────────────
msg="⚠️ Second Brain outcome check — ${#FAILS[@]} problem(s):"
for f in "${FAILS[@]}"; do msg="$msg"$'\n'"• $f"; done
# What still works matters as much as what broke: it tells you how far the
# damage spread without making you SSH in to find out.
if [ ${#OKS[@]} -gt 0 ]; then
  msg="$msg"$'\n'$'\n'"Still OK: ${OKS[*]}"
fi
msg="$msg"$'\n'"decisions: $dec_open open, $dec_ans answered"
note "ALERTING: ${#FAILS[@]} failure(s)"

last=$(cat "$ALERTF" 2>/dev/null || echo 0)
if [ $(( now - last )) -ge 3600 ]; then
  send "$msg" && echo "$now" >"$ALERTF"
else
  note "(alert throttled, last sent $(( (now - last) / 60 ))m ago)"
fi
exit 1
