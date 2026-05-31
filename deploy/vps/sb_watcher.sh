#!/bin/bash
# Second Brain file watcher: on new raw/ file, create a kanban ingest task.
# The dispatch daemon then routes it to secondbrain-agent (llm-wiki ingest).
set -u
export HOME=/root
export PATH=/usr/local/bin:/usr/bin:/bin
RAW=/root/SecondBrain/raw
HERMES=/usr/local/bin/hermes

inotifywait -m -e close_write -e moved_to --format '%f' "$RAW" 2>/dev/null | while read -r fname; do
  case "$fname" in
    .*|*.tmp|*.swp|*~|*.part) continue ;;
  esac
  case "$fname" in
    *.md|*.txt|*.pdf) ;;
    *) continue ;;
  esac
  sleep 2  # let the file finish writing
  [ -f "$RAW/$fname" ] || continue
  key="ingest-$(printf '%s' "$fname" | md5sum | cut -c1-12)"
  "$HERMES" kanban --board secondbrain create "Ingest: $fname" \
    --assignee secondbrain-agent \
    --workspace dir:/root/SecondBrain \
    --skill llm-wiki \
    --idempotency-key "$key" \
    --body "A new source file 'raw/$fname' was added. Ingest it into the wiki following the llm-wiki skill and wiki/SCHEMA.md: read SCHEMA.md and index.md first; check for existing related pages; create or update entity/concept/source pages using Title Case filenames WITH SPACES, required frontmatter, and at least 2 [[wikilinks]] each; update index.md; append an entry to log.md; then move raw/$fname to raw/processed/. Report every file created, updated, or moved." \
    >> /root/SecondBrain/outputs/watcher.log 2>&1
  echo "[$(date '+%F %T')] queued ingest task for $fname" >> /root/SecondBrain/outputs/watcher.log
done
