#!/bin/bash
# Second Brain voice-journal watcher: on a new audio file in journal/inbox/,
# transcribe it into the private journal via voice_journal.py. This is the
# journaling lane — separate from raw/ (the knowledge-wiki queue), so journal
# entries never touch the ingest agent or the wiki.
set -u
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin
INBOX=/root/SecondBrain/journal/inbox
PY=/root/SecondBrain/.venv/bin/python
VJ=/root/SecondBrain/scripts/voice_journal.py
LOG=/root/SecondBrain/outputs/journal.log
mkdir -p "$INBOX"
inotifywait -m -e close_write -e moved_to --format '%f' "$INBOX" 2>/dev/null | while read -r fname; do
  case "$fname" in .*|*.tmp|*.swp|*~|*.part) continue ;; esac
  case "$fname" in *.m4a|*.mp3|*.wav|*.ogg|*.opus|*.aac|*.flac|*.mp4|*.webm|*.3gp) ;; *) continue ;; esac
  sleep 2
  [ -f "$INBOX/$fname" ] || continue
  echo "[$(date '+%F %T')] journaling $fname" >>"$LOG"
  "$PY" "$VJ" "$INBOX/$fname" >>"$LOG" 2>&1 &   # background keeps watcher responsive
done
