#!/bin/bash
# Copy the demo vault to a scratch location so you can run a real ingest on it
# (e.g. while recording the README GIF) without touching the copy in the repo.
#
#   scripts/demo_reset.sh                 # resets ~/SecondBrainDemo
#   scripts/demo_reset.sh /path/to/vault  # or any other location
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$HOME/SecondBrainDemo}"

case "$TARGET" in
    ""|"/"|"$HOME"|"$HOME/SecondBrain") echo "Refusing to reset $TARGET"; exit 1 ;;
esac

rm -rf "$TARGET"
cp -R "$REPO_DIR/examples/demo-vault" "$TARGET"
echo "Demo vault ready at $TARGET"
echo "Ingest it with:"
echo "  SECOND_BRAIN_PATH=\"$TARGET\" python3 \"$REPO_DIR/auto_ingest.py\""
