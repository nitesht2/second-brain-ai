#!/usr/bin/env bash
# book_drip.sh — feed staged chunks into raw/ ONE at a time, only when idle.
# Kanban-free idle check: raw/ empty AND no sb_ingest running. Cron */10.
set -u
export TZ=America/Los_Angeles
VAULT=/root/SecondBrain; STAGING=$VAULT/_staging; RAW=$VAULT/raw
LOG=$VAULT/outputs/book_feed.log
ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
NEXT=$(find "$STAGING" -type f -name '*.md' 2>/dev/null | sort | head -1)
[ -z "$NEXT" ] && exit 0
# maxdepth 1 excludes raw/failed/ (quarantined files must not pin the drip shut)
RAWPEND=$(find "$RAW" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l)
INGESTING=$(pgrep -f 'scripts/sb_ingest.sh' 2>/dev/null | wc -l)
if [ "$RAWPEND" -eq 0 ] && [ "$INGESTING" -eq 0 ]; then
  bookslug=$(basename "$(dirname "$NEXT")")
  mv "$NEXT" "$RAW/book-$bookslug-$(basename "$NEXT")" && echo "$(ts) FED $(basename "$NEXT") (book=$bookslug)" >>"$LOG"
  rmdir "$(dirname "$NEXT")" 2>/dev/null
fi
exit 0
