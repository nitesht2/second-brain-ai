#!/usr/bin/env bash
# Run a Second Brain skill standalone (Pacific system-cron driven, DST-safe) and
# deliver the result to Discord via 'hermes send'. Decoupled from Hermes' UTC cron.
set -u
export TZ=America/Los_Angeles
SKILL=${1:?usage: run_brain_skill.sh <skill>}
V=/root/SecondBrain
LOG=$V/outputs/skill_runs.log
HB=/usr/local/bin/hermes
ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }

case "$SKILL" in
  morning-brief)      SUB=briefings; SUF=morning-brief; PROMPT='Run the morning-brief skill against the SecondBrain vault.';;
  connection-finder)  SUB=analyses;  SUF=connections;   PROMPT='Run the connection-finder skill against the SecondBrain vault.';;
  weekly-synthesis)   SUB=reviews;   SUF=weekly-synthesis; PROMPT='Run the weekly-synthesis skill against the SecondBrain vault. Update wiki/index.md priorities in place.';;
  thinking-partner)   SUB=analyses;  SUF=thinking-partner; PROMPT='Run the thinking-partner skill against the SecondBrain vault.';;
  *) echo "$(ts) ERROR unknown skill $SKILL" >> "$LOG"; exit 1;;
esac

cd "$V" || exit 1
MARK=$(mktemp); touch "$MARK"
echo "$(ts) START $SKILL" >> "$LOG"
timeout 600 "$HB" -p secondbrain-agent -z "$PROMPT" --skill "$SKILL" --yolo >/dev/null 2>&1
# hold the ingest lock so sanitize never races the agent's own index.md writes
[ -x /root/.hermes/scripts/wiki_sanitize.sh ] \
  && flock "$V/.ingest.lock" /root/.hermes/scripts/wiki_sanitize.sh \
  || echo "$(ts) WARN wiki_sanitize.sh missing" >> "$LOG"
OUT=$(find "$V/outputs/$SUB" -name "*$SUF*.md" -newer "$MARK" 2>/dev/null | head -1)
rm -f "$MARK"
if [ -n "$OUT" ]; then
  "$HB" -p secondbrain-agent send -t discord -f "$OUT" -s "[$SKILL] $(date '+%a %b %d %I:%M%p %Z')" -q 2>>"$LOG" \
    && echo "$(ts) OK $SKILL -> delivered $(basename "$OUT")" >> "$LOG" \
    || echo "$(ts) WARN $SKILL ran but delivery failed ($OUT)" >> "$LOG"
else
  echo "$(ts) WARN $SKILL produced no fresh output" >> "$LOG"
fi
exit 0
