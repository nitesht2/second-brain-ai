#!/usr/bin/env bash
# sb_ingest.sh <filename-in-raw> — ingest ONE raw file directly (no kanban).
# Serialized via flock (one at a time), timeout-guarded. raw/ = queue,
# raw/processed/ = audit trail. Replaces the kanban task+dispatcher path.
set -u
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin
F=${1:?usage: sb_ingest.sh <filename-in-raw>}
V=/root/SecondBrain; RAW=$V/raw; HB=/usr/local/bin/hermes
LOG=$V/outputs/ingest_runs.log; LOCK=$V/.ingest.lock
ts(){ date '+%F %T'; }
[ -f "$RAW/$F" ] || { echo "$(ts) skip (gone): $F" >>"$LOG"; exit 0; }
PROMPT="A new source file 'raw/$F' was added. Ingest it into the wiki following the llm-wiki skill and wiki/SCHEMA.md: read SCHEMA.md and index.md first; check for existing related pages; create or update entity/concept/source pages using Title Case filenames WITH SPACES, required frontmatter, and at least 2 [[Exact Page Title]]-style links each; update index.md; append an entry to log.md; then move raw/$F to raw/processed/. Report every file created, updated, or moved."
exec 9>"$LOCK"; flock 9          # serialize: one ingest at a time
echo "$(ts) START $F" >>"$LOG"
cd "$V" || exit 1
timeout 600 "$HB" -p secondbrain-agent -z "$PROMPT" --skill llm-wiki --yolo >>"$LOG" 2>&1
rc=$?
/root/.hermes/scripts/wiki_sanitize.sh
if [ ! -f "$RAW/$F" ]; then echo "$(ts) OK $F (rc=$rc -> processed)" >>"$LOG"
else echo "$(ts) INCOMPLETE $F (rc=$rc, still in raw, will retry)" >>"$LOG"; fi
exit 0
