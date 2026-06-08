#!/usr/bin/env bash
# Strip stray leading pipes from index/log bullet lists (never tables -> leading | = corruption). Idempotent.
set -u
W=/root/SecondBrain/wiki
sed -i -e 's/^|\+//' -e 's/^ *\[\[/- [[/' "$W/index.md" "$W/log.md" 2>/dev/null
