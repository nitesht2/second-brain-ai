#!/usr/bin/env bash
# Daily vault backup -> GitHub (prevents the May-17 staleness recurrence).
set -u
V=/root/SecondBrain
LOG=$V/outputs/vault_backup.log
ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
cd "$V" || exit 0
# snapshot the live profile (SOUL + config) so DR has the exact current behavior
mkdir -p "$V/_profile"
cp -f /root/.hermes/profiles/secondbrain-agent/SOUL.md "$V/_profile/SOUL.md" 2>/dev/null
cp -f /root/.hermes/profiles/secondbrain-agent/config.yaml "$V/_profile/config.yaml" 2>/dev/null
git add -A 2>/dev/null
if git diff --cached --quiet 2>/dev/null; then
  echo "$(ts) no changes" >> "$LOG"; exit 0
fi
git commit -m "Auto-backup: $(ts)" >/dev/null 2>&1
if git push origin main >/dev/null 2>&1; then
  echo "$(ts) pushed $(git rev-parse --short HEAD)" >> "$LOG"
else
  echo "$(ts) ALERT push failed (commit $(git rev-parse --short HEAD) local-only)" >> "$LOG"
fi
exit 0
