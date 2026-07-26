#!/bin/bash
# Second Brain file watcher (kanban-free): on new raw/ file, ingest it directly
# via sb_ingest.sh (flock-serialized). raw/ = queue, raw/processed/ = audit trail.
set -u
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin
RAW=/root/SecondBrain/raw
ING=/root/SecondBrain/scripts/sb_ingest.sh
LOG=/root/SecondBrain/outputs/watcher.log
mkdir -p "$RAW"
# stderr NOT discarded: a missing dir or inotify error must show in the journal, not die silently
inotifywait -m -e close_write -e moved_to --format '%f' "$RAW" | while read -r fname; do
  case "$fname" in .*|*.tmp|*.swp|*~|*.part) continue ;; esac
  case "$fname" in *.md|*.txt|*.pdf) ;; *) continue ;; esac
  sleep 2
  [ -f "$RAW/$fname" ] || continue
  "$ING" "$fname" >>"$LOG" 2>&1 &   # flock inside serializes; background keeps watcher responsive
  echo "[$(date '+%F %T')] dispatched ingest for $fname (kanban-free)" >>"$LOG"
done
