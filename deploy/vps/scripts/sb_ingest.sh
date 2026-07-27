#!/usr/bin/env bash
# sb_ingest.sh <filename-in-raw> — ingest ONE raw file directly (no kanban).
# Serialized via flock (one at a time), timeout-guarded. raw/ = queue,
# raw/processed/ = audit trail. Replaces the kanban task+dispatcher path.
set -u
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin
F=${1:?usage: sb_ingest.sh <filename-in-raw>}
V=/root/SecondBrain; RAW=$V/raw; CLAUDE=/usr/local/bin/claude
LOG=$V/outputs/ingest_runs.log; LOCK=$V/.ingest.lock
ATTEMPTS=$V/.ingest_attempts
ts(){ date '+%F %T'; }
# Engine is Claude Code (Max subscription), not hermes: hermes runs on a
# metered provider whose balance ran out on 2026-07-06, silently stalling every
# ingest for weeks. llm-wiki was a hermes builtin and does not carry over, so
# the schema rules it enforced are spelled out in the prompt instead.
PROMPT="A new source file 'raw/$F' was added. Ingest it into the wiki following wiki/SCHEMA.md: read SCHEMA.md and index.md first; check for existing related pages; create or update entity/concept/source pages using Title Case filenames WITH SPACES, required frontmatter, and at least 2 [[Exact Page Title]]-style links each; update index.md; append an entry to log.md; then move raw/$F to raw/processed/. Report every file created, updated, or moved."
exec 9>"$LOCK" || { echo "$(ts) FATAL cannot open lock $LOCK" >>"$LOG"; exit 1; }
flock 9 || { echo "$(ts) FATAL flock failed on $LOCK" >>"$LOG"; exit 1; }   # serialize: one ingest at a time
# existence check AFTER the lock: a queued run may already have processed this file
[ -f "$RAW/$F" ] || { echo "$(ts) skip (gone): $F" >>"$LOG"; exit 0; }
echo "$(ts) START $F" >>"$LOG"
cd "$V" || exit 1
# Tools are scoped rather than bypassed: raw/ is built from bookmarked web
# pages, so this prompt carries attacker-influenceable text into an agent
# running as root. acceptEdits + an explicit tool list keeps the blast radius
# at the vault instead of the box. 900s: Claude Code is slower than hermes was.
timeout 900 "$CLAUDE" -p "$PROMPT" \
  --allowedTools Read Write Edit Glob Grep Bash \
  --permission-mode acceptEdits >>"$LOG" 2>&1
rc=$?
[ -x /root/.hermes/scripts/wiki_sanitize.sh ] && /root/.hermes/scripts/wiki_sanitize.sh || echo "$(ts) WARN wiki_sanitize.sh missing" >>"$LOG"
# Success needs BOTH: the agent exited clean AND the file left raw/. Checking
# only the file logged "OK (rc=1)" whenever a failed run still moved it, which
# is how 9 days of dead-provider failures read as successes.
if [ ! -f "$RAW/$F" ] && [ "$rc" -eq 0 ]; then
  echo "$(ts) OK $F (rc=$rc -> processed)" >>"$LOG"
  rm -f "$ATTEMPTS/$F.count"
  exit 0
fi
if [ ! -f "$RAW/$F" ]; then   # gone but rc!=0: agent moved it then failed
  echo "$(ts) MOVED-BUT-FAILED $F (rc=$rc; check raw/processed/)" >>"$LOG"
  rm -f "$ATTEMPTS/$F.count"
  exit 1
fi
# still in raw/ -> failed attempt; cap retries, quarantine after 3
mkdir -p "$ATTEMPTS"
n=$(cat "$ATTEMPTS/$F.count" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" >"$ATTEMPTS/$F.count"
if [ "$n" -ge 3 ]; then
  mkdir -p "$RAW/failed"
  mv "$RAW/$F" "$RAW/failed/$F"
  rm -f "$ATTEMPTS/$F.count"
  echo "$(ts) QUARANTINED $F (rc=$rc, attempt $n -> raw/failed/)" >>"$LOG"
else
  echo "$(ts) INCOMPLETE $F (rc=$rc, attempt $n/3, still in raw, will retry)" >>"$LOG"
fi
exit 1
