#!/bin/bash
# Second Brain File Watcher
# Monitors ~/SecondBrain/raw/ for new files and creates kanban tasks.
# Runs as a launchd daemon. Dual-trigger: cron fallback every 6h catches misses.

VAULT="$HOME/SecondBrain"
RAW_DIR="$VAULT/raw"
HERMES_BIN="$HOME/.local/bin/hermes"
LOG="$VAULT/outputs/watcher.log"

# Ensure vault exists
mkdir -p "$RAW_DIR" "$VAULT/outputs"

# Watch for new files and trigger ingest
fswatch -0 "$RAW_DIR" | while read -d "" event; do
    # Skip if it's a directory or in processed/
    if [ -d "$event" ] || echo "$event" | grep -q "/processed/"; then
        continue
    fi

    filename="$(basename "$event")"

    # Skip hidden files and temp files
    case "$filename" in
        .*|*.tmp|*.swp|*~) continue ;;
    esac

    # Small delay to let the file finish writing
    sleep 2

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] New file detected: $filename"

    # Create kanban task if hermes is available
    # CLI form: hermes kanban [--board <slug>] create [--body ...] [--assignee ...] <title>
    if [ -f "$HERMES_BIN" ]; then
        "$HERMES_BIN" kanban --board secondbrain create "Ingest: $filename" \
            --body "Auto-detected file in raw/: $filename" \
            --assignee secondbrain-agent >>"$LOG" 2>&1 \
            || echo "kanban create failed for $filename" >>"$LOG"
    fi
done
