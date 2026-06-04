#!/usr/bin/env bash
# book_drip.sh — feed staged book chapters into the ingest pipeline ONE at a time,
# ONLY when the pipeline is idle (adaptive backpressure). Cron: every 10 min.
# Usage: book_drip.sh [--dry-run]
set -u
export TZ=America/Los_Angeles
VAULT=/root/SecondBrain
BOOKS=$VAULT/books
RAW=$VAULT/raw
LOG=$VAULT/outputs/book_feed.log
HB=/usr/local/bin/hermes
DRY=${1:-}
ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }

# next staged chapter (lowest book dir, lowest chapter number)
NEXT=$(find "$BOOKS" -type f -name '*.md' 2>/dev/null | sort | head -1)
[ -z "$NEXT" ] && exit 0   # nothing staged

# pipeline idle? (kanban ready + running == 0, and DB not corrupt)
STATS=$("$HB" kanban --board secondbrain stats 2>&1)
echo "$STATS" | grep -qiE 'corrupt|integrity' && { echo "$(ts) SKIP kanban unhealthy" >> "$LOG"; exit 0; }
READY=$(echo "$STATS" | awk '/ready/{print $2; exit}'); RUN=$(echo "$STATS" | awk '/running/{print $2; exit}')
READY=${READY:-0}; RUN=${RUN:-0}
RAWPEND=$(find "$RAW" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l)

if [ "$READY" -eq 0 ] 2>/dev/null && [ "$RUN" -eq 0 ] 2>/dev/null && [ "$RAWPEND" -eq 0 ]; then
  bookslug=$(basename "$(dirname "$NEXT")")
  dest="$RAW/book-$bookslug-$(basename "$NEXT")"
  if [ "$DRY" = '--dry-run' ]; then
    echo "$(ts) DRY would feed: $NEXT -> $dest (idle: ready=$READY run=$RUN rawpend=$RAWPEND)"
  else
    mv "$NEXT" "$dest" && echo "$(ts) FED $(basename "$NEXT") (book=$bookslug)" >> "$LOG"
    # cleanup empty book dir
    rmdir "$(dirname "$NEXT")" 2>/dev/null
  fi
else
  [ "$DRY" = '--dry-run' ] && echo "$(ts) DRY pipeline busy (ready=$READY run=$RUN rawpend=$RAWPEND) — would wait"
fi
exit 0
