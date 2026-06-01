#!/bin/bash
# Mac -> VPS auto-push: when a new file lands in ~/SecondBrain/raw/ (e.g. Obsidian
# Web Clipper), scp it to the VPS raw/ where the agent ingests it.
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
RAW="$HOME/SecondBrain/raw"
VPS="${BRAIN_VPS_HOST:-root@YOUR_VPS_IP}"
VPS_RAW="/root/SecondBrain/raw/"
LOG="$HOME/SecondBrain/outputs/mac-push.log"
mkdir -p "$RAW" "$(dirname "$LOG")"
echo "[$(date '+%F %T')] mac-push watcher started on $RAW" >> "$LOG"
fswatch -0 "$RAW" | while read -d "" path; do
  case "$path" in */processed/*|*/generated/*|*/.*) continue;; esac
  fname="$(basename "$path")"
  case "$fname" in
    .*|*.tmp|*.swp|*~|*.part|*.crdownload) continue;;
    *.md|*.txt|*.pdf) ;;
    *) continue;;
  esac
  [ -f "$path" ] || continue
  sleep 2  # let the file finish writing
  if scp -q "$path" "$VPS:$VPS_RAW" 2>>"$LOG"; then
    echo "[$(date '+%F %T')] pushed -> VPS: $fname" >> "$LOG"
  else
    echo "[$(date '+%F %T')] FAILED push: $fname" >> "$LOG"
  fi
done
