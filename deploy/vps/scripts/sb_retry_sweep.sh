#!/usr/bin/env bash
# sb_retry_sweep.sh — re-ingest any raw file lingering (failed/missed by watcher).
# Cron */15. flock in sb_ingest serializes vs the watcher.
set -u
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin
RAW=/root/SecondBrain/raw; ING=/root/SecondBrain/scripts/sb_ingest.sh; now=$(date +%s)
for f in "$RAW"/*.md; do
  [ -f "$f" ] || continue
  [ $(( now - $(stat -c %Y "$f") )) -lt 180 ] && continue   # still arriving
  "$ING" "$(basename "$f")"
done
