#!/usr/bin/env bash
# sb_decision_prep.sh — turn the week's captures into decisions you have to answer.
#
# The vault holds 2,201 pages and 3 decisions. Capture is automated; concluding is
# not, so it does not happen. This does the part that can be automated: reading the
# week and finding the real tensions in it. It deliberately does NOT write decision
# pages. It asks questions and leaves them for you, because a vault full of
# machine-written "decisions" is worth less than three real ones.
#
# Sunday 09:00 PT. Output goes to Discord and to outputs/, never straight to wiki/.
set -u
export TZ=America/Los_Angeles
export HOME=/root PATH=/usr/local/bin:/usr/bin:/bin

V=/root/SecondBrain
LOG=$V/outputs/decision_prep.log
OUTDIR=$V/outputs
HB=/usr/local/bin/hermes
CLAUDE=/usr/local/bin/claude
MIN_SOURCES=3          # under this, the week was too quiet to be worth your 20 minutes
STAMP=$(date +%Y-%m-%d)
OUT=$OUTDIR/decision-prep-$STAMP.md

ts(){ date '+%Y-%m-%dT%H:%M:%S%z'; }
note(){ echo "$(ts) $1" >>"$LOG"; }

cd "$V" || exit 0
mkdir -p "$OUTDIR"

# ── what landed this week ──────────────────────────────────────────────────
mapfile -t NEW < <(find "$V/wiki/sources" "$V/wiki/concepts" -name '*.md' -mtime -7 2>/dev/null | sort)
if [ "${#NEW[@]}" -lt "$MIN_SOURCES" ]; then
  note "quiet week (${#NEW[@]} new pages, need $MIN_SOURCES) — skipping"
  exit 0
fi
note "preparing from ${#NEW[@]} new pages"

# Titles plus the first real line of each, enough for the model to see themes
# without pulling the whole week into context.
DIGEST=$(for f in "${NEW[@]}"; do
  title=$(basename "$f" .md)
  gist=$(sed -e '1,/^---$/d' -e '/^---$/,$!d' "$f" 2>/dev/null | grep -vE '^\s*$|^#|^\*\*|^---' | head -1 | cut -c1-160)
  [ -z "$gist" ] && gist=$(grep -vE '^\s*$|^#|^---|^[a-z_]+:' "$f" | head -1 | cut -c1-160)
  echo "- ${title}: ${gist}"
done | head -80)

PROMPT="You are preparing Nitesh's weekly review of his knowledge vault. Below are the pages captured this week.

Your job is NOT to summarize them and NOT to draw conclusions for him. It is to find the three decisions this week's material actually forces, and put them to him as questions he can answer in a couple of minutes each.

A good item here:
- names a real tension or tradeoff visible in the material, not a topic
- is phrased as a question with at least two defensible answers
- cites the specific pages it came from by title
- connects to what he actually does: data engineering at Living Spaces, NiteshTechAI on X, the Sleep Focus Meditation and Finance Major channels, his trading bot, or the Second Brain itself
- is worth deciding, meaning the answer changes what he builds or ships next

Skip anything that is merely interesting. If the week only supports one or two real decisions, give one or two. Padding to three is worse than giving one.

Format exactly:

## Decision 1: <the question>
**Why it came up:** <2 sentences, citing page titles>
**The tension:** <the two or more defensible positions, one line each>
**If you decide, write:** wiki/decisions/<suggested filename>.md

Then a final section:

## Skipped
<one line naming themes you deliberately did not raise, so he can tell what you ignored>

This week's pages (${#NEW[@]} total):
$DIGEST"

note "invoking claude"
if ! timeout 900 "$CLAUDE" -p "$PROMPT" \
      --allowedTools Read Glob Grep \
      --permission-mode acceptEdits > "$OUT.tmp" 2>>"$LOG"; then
  note "ALERT claude failed, see log"
  rm -f "$OUT.tmp"
  echo "⚠️ Second Brain: weekly decision prep failed to run" | "$HB" -p secondbrain-agent send -t discord -q 2>>"$LOG"
  exit 1
fi

{
  echo "# Decision prep — week ending $STAMP"
  echo
  echo "_From ${#NEW[@]} pages captured this week. These are questions, not answers._"
  echo "_Answer one and write it to wiki/decisions/. Three months of vault has three decisions in it._"
  echo
  cat "$OUT.tmp"
} > "$OUT"
rm -f "$OUT.tmp"
note "wrote $OUT ($(wc -l < "$OUT") lines)"

# Discord gets the file so it is readable on a phone Sunday morning
if "$HB" -p secondbrain-agent send -t discord -f "$OUT" -q 2>>"$LOG"; then
  note "posted to discord"
else
  note "ALERT discord post failed"
fi
exit 0
