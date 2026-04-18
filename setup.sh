#!/bin/bash
# Second Brain AI - Quick Setup Script
# Creates vault, copies templates, installs slash commands, sets up launchd scheduler + save server

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="$HOME/SecondBrain"
CLAUDE_COMMANDS="$HOME/.claude/commands"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"

echo ""
echo "🧠 Second Brain AI — Quick Setup"
echo "================================="
echo ""

# Step 1: Create vault structure
echo "📁 Step 1/5: Creating vault at $VAULT..."
mkdir -p "$VAULT"/{raw/processed,wiki/{entities,concepts,sources,synthesis},outputs}
echo "    ✓ Done"

# Step 2: Copy vault template files
echo "📋 Step 2/6: Copying vault template files..."
cp -n "$REPO_DIR/vault-template/CLAUDE.md" "$VAULT/" 2>/dev/null || true
cp -n "$REPO_DIR/vault-template/wiki/index.md" "$VAULT/wiki/" 2>/dev/null || true
cp -n "$REPO_DIR/vault-template/wiki/log.md" "$VAULT/wiki/" 2>/dev/null || true
cp "$REPO_DIR/auto_ingest.py" "$VAULT/"
cp "$REPO_DIR/brain_server.py" "$VAULT/"
echo "    ✓ Done"

# Step 3: Install Claude Code slash commands
echo "🤖 Step 3/6: Installing slash commands to $CLAUDE_COMMANDS..."
mkdir -p "$CLAUDE_COMMANDS"
cp "$REPO_DIR/claude-commands/"*.md "$CLAUDE_COMMANDS/"
echo "    ✓ /second-brain, /second-brain-ingest, /second-brain-query, /second-brain-lint, /second-brain-synthesis"

# Step 4: Install launchd scheduler
echo "⏰ Step 4/6: Installing launchd scheduler (every 2 days at 4:07am)..."
cp "$REPO_DIR/launchd/com.nitesh.secondbrain-ingest.plist" "$LAUNCHD_DIR/"
launchctl unload "$LAUNCHD_DIR/com.nitesh.secondbrain-ingest.plist" 2>/dev/null || true
launchctl load "$LAUNCHD_DIR/com.nitesh.secondbrain-ingest.plist"
echo "    ✓ Scheduler active"

# Step 5: Install save server (1-click bookmarklet backend)
echo "🔗 Step 5/6: Installing save server (port 7331)..."
cp "$REPO_DIR/launchd/com.nitesh.secondbrain-server.plist" "$LAUNCHD_DIR/"
launchctl unload "$LAUNCHD_DIR/com.nitesh.secondbrain-server.plist" 2>/dev/null || true
launchctl load "$LAUNCHD_DIR/com.nitesh.secondbrain-server.plist"
echo "    ✓ Save server running at http://localhost:7331"

# Step 6: Check prerequisites
echo "🔍 Step 6/6: Checking prerequisites..."
if command -v ollama &>/dev/null; then
    echo "    ✓ Ollama installed"
    if ollama list 2>/dev/null | grep -q "gemma3:4b\|qwen3.5"; then
        echo "    ✓ AI model available"
    else
        echo "    ⚠ No model found. Run: ollama pull gemma3:4b"
    fi
else
    echo "    ⚠ Ollama not found. Install from https://ollama.com"
fi

if [ -d "/Applications/Obsidian.app" ]; then
    echo "    ✓ Obsidian installed"
else
    echo "    ⚠ Obsidian not found. Install from https://obsidian.md"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Open Obsidian → Open folder as vault → select $VAULT"
echo "  2. Install Web Clipper (https://obsidian.md/clipper) → set location to 'raw'"
echo "  3. Add the YouTube bookmarklet to your browser:"
echo ""
echo "     Drag this link to your bookmarks bar, or create a new bookmark with this URL:"
echo ""
echo "     javascript:(function(){fetch('http://localhost:7331/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:location.href,title:document.title})}).then(r=>r.json()).then(d=>alert('✅ Saved to Second Brain: '+d.file)).catch(()=>alert('❌ Save server not running'));})();"
echo ""
echo "  4. In Claude Code, run: /second-brain"
echo ""
echo "Test save server:"
echo "  curl -s http://localhost:7331/save -X POST -H 'Content-Type: application/json' \\"
echo "    -d '{\"url\":\"https://youtube.com/watch?v=test\",\"title\":\"Test\"}'"
echo ""
