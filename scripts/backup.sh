#!/bin/bash
# Second Brain Backup
# Copies vault to timestamped directory, excluding raw/processed and outputs/
set -e

VAULT="$HOME/SecondBrain"
BACKUP_DIR="$HOME/SecondBrain-Backups"

TIMESTAMP=$(date +%Y-%m-%d_%H%M)
DEST="$BACKUP_DIR/vault-$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

# Rsync vault, excluding large generated files
rsync -a --exclude 'raw/processed/' --exclude 'outputs/' --exclude '.obsidian/' \
    "$VAULT/" "$DEST/"

echo "✅ Backed up to $DEST"

# Keep only last 30 backups (null-delimited so paths with spaces survive xargs)
ls -dt "$BACKUP_DIR"/vault-* 2>/dev/null | tail -n +31 | tr '\n' '\0' | xargs -0 rm -rf 2>/dev/null || true
echo "📦 $(ls "$BACKUP_DIR" | wc -l) backups retained"
