#!/bin/bash
# Second Brain File Watcher
# Monitors ~/SecondBrain/raw/ for new files and creates kanban tasks.
# Runs as a launchd daemon. Dual-trigger: cron fallback every 6h catches misses.

VAULT="$HOME/SecondBrain"
RAW_DIR="$VAULT/raw"
HERMES_BIN="$HOME/.local/bin/hermes"

# Ensure vault exists
mkdir -p "$RAW_DIR"

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
    if [ -f "$HERMES_BIN" ]; then
        "$HERMES_BIN" kanban create \
            --board secondbrain \
            --title "Ingest: $filename" \
            --description "Auto-detected file in raw/. Process and extract into wiki." \
            --assignee secondbrain-agent 2>/dev/null || true
    fi
done
