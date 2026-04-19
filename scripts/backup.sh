#!/bin/bash
# Second Brain — nightly local + GitHub backup
# Local: ~/Backups/SecondBrain/ (3-day rolling window)
# Remote: github.com/nitesht2/second-brain-vault (infinite git history)

set -e
VAULT="$HOME/SecondBrain"
BACKUP_DIR="$HOME/Backups/SecondBrain"
STAMP=$(date +%Y-%m-%d)

# --- 1. Local tarball snapshot ---
mkdir -p "$BACKUP_DIR"
# Back up wiki + brand + outputs (content only, not raw/ which is ephemeral)
tar -czf "$BACKUP_DIR/vault-$STAMP.tar.gz" -C "$VAULT" wiki brand outputs 2>/dev/null

# --- 2. Prune: keep only last 3 days of local snapshots ---
ls -1t "$BACKUP_DIR"/vault-*.tar.gz 2>/dev/null | tail -n +4 | xargs -I {} rm -f {}

# --- 3. GitHub sync (private repo) ---
cd "$VAULT"
git add wiki brand outputs/cost-log.md .gitignore 2>/dev/null || true
if ! git diff --cached --quiet; then
    git commit -m "Auto-backup: $STAMP" --quiet
    git push --quiet 2>/dev/null || echo "[$(date)] GitHub push failed — local backup still succeeded" >> "$BACKUP_DIR/backup.log"
fi

echo "[$(date)] Backup complete: $BACKUP_DIR/vault-$STAMP.tar.gz" >> "$BACKUP_DIR/backup.log"
