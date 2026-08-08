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
# hold the ingest lock so sanitize never races the agent's own index.md writes
[ -x /root/.hermes/scripts/wiki_sanitize.sh ] \
  && flock "$V/.ingest.lock" /root/.hermes/scripts/wiki_sanitize.sh \
  || echo "$(ts) WARN wiki_sanitize.sh missing" >> "$LOG"
git add -A 2>/dev/null
# "nothing staged" is NOT the same as "nothing to do": after a failed push the
# commit exists but nothing is staged, so exiting here stranded it permanently
# (2026-07-27, a day of wiki work sat local-only while the log said "no changes").
# Only skip when the working tree is clean AND we are not ahead of the remote.
git fetch origin main >/dev/null 2>&1
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
if git diff --cached --quiet 2>/dev/null && [ "${AHEAD:-0}" -eq 0 ]; then
  echo "$(ts) no changes" >> "$LOG"; exit 0
fi
# Commit BEFORE rebasing. `git pull --rebase` refuses to run with a dirty index,
# so rebasing first fails in exactly the one situation the rebase exists for:
# local work staged AND the remote moved. On 2026-08-02 the Mac pushed, and every
# run from then on aborted here with 14 pages of wiki work staged but never
# committed, logging ALERT and exiting 0 so systemd recorded a success.
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "Auto-backup: $(ts)" >/dev/null 2>&1 \
    || { echo "$(ts) ALERT commit failed (git identity? staged state kept)" >> "$LOG"; exit 1; }
fi
# Diverged remote (the Mac pushes to this repo too) rejects a plain push, so
# replay our commits on top before trying. Conflicts abort rather than guess.
if [ "$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)" -gt 0 ]; then
  if ! git -c user.email=vps@secondbrain -c user.name='SecondBrain VPS' \
        pull --rebase origin main >/dev/null 2>&1; then
    git rebase --abort >/dev/null 2>&1
    echo "$(ts) ALERT remote diverged and rebase failed, manual merge needed" >> "$LOG"
    exit 1
  fi
  echo "$(ts) rebased onto origin/main before push" >> "$LOG"
fi
# HEAD:main pushes the commit we just made even if HEAD sits on another branch
if git push origin HEAD:main >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1
  if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main 2>/dev/null)" ]; then
    echo "$(ts) pushed $(git rev-parse --short HEAD)" >> "$LOG"
  else
    echo "$(ts) ALERT push verify failed (origin/main != HEAD $(git rev-parse --short HEAD))" >> "$LOG"
  fi
else
  echo "$(ts) ALERT push failed (commit $(git rev-parse --short HEAD) local-only)" >> "$LOG"
  exit 1
fi
exit 0
