#!/usr/bin/env bash
# Strip stray leading pipes from index/log bullet lists. Idempotent.
# Table-safe: lines shaped like table rows (| ... |) are left untouched, so
# markdown tables survive. Known limitation: fenced code blocks are not
# excluded, so pipe/wikilink-shaped lines inside fences can still be rewritten.
set -u
W=/root/SecondBrain/wiki
sed -i -e '/^|.*|/!s/^|\+//' -e '/^|.*|/!s/^ *\[\[/- [[/' "$W/index.md" "$W/log.md" 2>/dev/null
