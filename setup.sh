#!/bin/bash
# Second Brain AI — Quick Setup
# Creates vault, installs launchd services, file watcher, daily digest.
# One command: git clone && ./setup.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="$HOME/SecondBrain"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
HERMES_BIN="$HOME/.local/bin/hermes"

echo ""
echo "🧠 Second Brain AI — Quick Setup"
echo "================================="
echo ""

# Step 1: Create vault structure
echo "📁 Step 1/7: Creating vault at $VAULT..."
mkdir -p "$VAULT"/{raw/processed,raw/generated,wiki/{entities,concepts,sources,synthesis},wiki/episodic,wiki/projects,outputs}
echo "    ✓ Done"

# Step 2: Set up directories early (needed for script copies)
echo "📋 Step 2/7: Setting up directories..."
mkdir -p "$HOME/.hermes/scripts"
mkdir -p "$HOME/.hermes/data/feeds"
echo '{}' > "$HOME/.hermes/data/feeds/seen.json"
echo "    ✓ Done"

# Step 3: Copy vault template and scripts
echo "📋 Step 3/7: Copying vault template and scripts..."
cp -n "$REPO_DIR/vault-template/CLAUDE.md" "$VAULT/" 2>/dev/null || true
cp -n "$REPO_DIR/vault-template/wiki/index.md" "$VAULT/wiki/" 2>/dev/null || true
cp -n "$REPO_DIR/vault-template/wiki/log.md" "$VAULT/wiki/" 2>/dev/null || true
cp "$REPO_DIR/auto_ingest.py" "$VAULT/"
cp "$REPO_DIR/scripts/daily_digest.py" "$HOME/.hermes/scripts/"
cp "$REPO_DIR/scripts/file_watcher.sh" "$HOME/.hermes/scripts/"
chmod +x "$HOME/.hermes/scripts/file_watcher.sh"
echo "    ✓ Done"

# Step 4: Install Python dependencies
echo "🐍 Step 4/7: Installing Python dependencies..."
if [ -f "$REPO_DIR/requirements.txt" ]; then
    pip3 install --break-system-packages -r "$REPO_DIR/requirements.txt" 2>/dev/null || \
        pip3 install -r "$REPO_DIR/requirements.txt" 2>/dev/null || \
        echo "    ⚠ pip install failed — install manually: pip3 install -r requirements.txt"
fi
echo "    ✓ Done"

# Step 5: Install launchd services
echo "⏰ Step 5/7: Installing launchd services..."
for plist in "$REPO_DIR/launchd/"*.plist; do
    name="$(basename "$plist")"
    # Replace $HOME in plist with actual home path
    sed "s|\$HOME|$HOME|g" "$plist" > "$LAUNCHD_DIR/$name"
    launchctl unload "$LAUNCHD_DIR/$name" 2>/dev/null || true
    launchctl load "$LAUNCHD_DIR/$name"
    echo "    ✓ $name"
done

# Step 6: Set up file watcher
echo "👀 Step 5/6: Setting up file watcher..."
if command -v fswatch &>/dev/null; then
    echo "    ✓ fswatch already installed"
else
    echo "    Installing fswatch via Homebrew..."
    brew install fswatch 2>/dev/null || echo "    ⚠ Install manually: brew install fswatch"
fi
echo "    ✓ File watcher installed at ~/.hermes/scripts/file_watcher.sh"

# Step 7: Check prerequisites
echo "🔍 Step 6/6: Checking prerequisites..."

MISSING=0

if [ -f "/Applications/Obsidian.app/Contents/MacOS/Obsidian" ]; then
    echo "    ✓ Obsidian installed"
else
    echo "    ⚠ Obsidian not found. Install from https://obsidian.md"
    MISSING=1
fi

if command -v python3 &>/dev/null; then
    echo "    ✓ Python 3 installed"
else
    echo "    ⚠ Python 3 not found"
    MISSING=1
fi

if [ -f "$HERMES_BIN" ]; then
    echo "    ✓ Hermes Agent installed"
else
    echo "    ⚠ Hermes Agent not found at $HERMES_BIN"
    echo "      Install: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
fi

if command -v fswatch &>/dev/null; then
    echo "    ✓ fswatch installed"
else
    echo "    ⚠ fswatch not found. Install: brew install fswatch"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open Obsidian → Open folder as vault → select $VAULT"
echo "  2. Install Obsidian Web Clipper → set vault location to '$VAULT'"
echo "  3. Drop a file into $VAULT/raw/ — the file watcher picks it up"
echo "  4. Browse $VAULT/wiki/ in Obsidian to see your knowledge graph"
echo ""
echo "Services running:"
echo "  • SecondBrain ingest    — daily at 4:07 AM (launchd)"
echo "  • File watcher          — real-time (launchd)"
echo "  • Daily digest          — 6 AM (cron via launchd)"
echo ""
echo "Docs: $VAULT/CLAUDE.md"
echo "Repo: https://github.com/nitesht2/second-brain-ai"
echo ""
