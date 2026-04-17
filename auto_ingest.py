#!/usr/bin/env python3
"""
Second Brain Auto-Ingest via Local LLM (Ollama)

Scans ~/SecondBrain/raw/ for unprocessed .md files and ingests them
using a local model (qwen3.5:9b) — zero Claude Code tokens.

Usage:
    python3 auto_ingest.py           # normal run
    python3 auto_ingest.py --dry-run # preview only, no writes
"""

import os
import re
import sys
import json
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

VAULT       = Path.home() / "SecondBrain"
RAW_DIR     = VAULT / "raw"
PROCESSED   = RAW_DIR / "processed"
WIKI_DIR    = VAULT / "wiki"
LOG_FILE    = VAULT / "outputs" / "ingest-log.md"

OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
MODEL           = "gemma3:4b"         # reliable structured output; qwen3.5:* also works (answer is in 'thinking' field)
TEMPERATURE     = 0.2                 # low = more consistent structure
MAX_TOKENS      = 3000
RAW_CHUNK       = 3500                # chars fed to model per file
LAST_RUN_FILE   = VAULT / "outputs" / ".last_ingest_run"
MIN_HOURS       = 48                  # skip if last run was less than this many hours ago

DRY_RUN     = "--dry-run" in sys.argv

# ── Helpers ───────────────────────────────────────────────────────────────────

def should_run_today() -> bool:
    """Return True if at least MIN_HOURS have passed since the last run."""
    if DRY_RUN:
        return True
    if not LAST_RUN_FILE.exists():
        return True
    import time
    last = float(LAST_RUN_FILE.read_text().strip())
    hours_since = (time.time() - last) / 3600
    if hours_since < MIN_HOURS:
        print(f"Last run was {hours_since:.1f}h ago (< {MIN_HOURS}h). Skipping.")
        return False
    return True


def record_run():
    """Stamp the current time as the last successful run."""
    import time
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(str(time.time()))


def get_raw_files():
    """Return all .md files in raw/ that are not inside processed/."""
    files = []
    for p in RAW_DIR.rglob("*.md"):
        if "processed" not in p.parts:
            files.append(p)
    return sorted(files)


def get_existing_wiki_stems():
    """Return list of existing wiki entry names (file stems, no .md)."""
    stems = []
    for p in WIKI_DIR.rglob("*.md"):
        stems.append(p.stem)
    return sorted(set(stems))


def call_ollama(prompt: str) -> str:
    """Call Ollama REST API and return the response text."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
        }
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read())
            # qwen3.* thinking models put the final answer in 'thinking' and leave 'response' empty
            text = body.get("response", "").strip()
            if not text:
                text = body.get("thinking", "").strip()
            return text
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama not reachable: {e}")


def build_prompt(content: str, filename: str, existing: list) -> str:
    """Build the ingest prompt, injecting existing wiki names for wikilinks."""
    existing_sample = "\n".join(f"  - [[{e}]]" for e in existing[:60])
    snippet = content[:RAW_CHUNK]
    if len(content) > RAW_CHUNK:
        snippet += "\n... [truncated]"

    return f"""You are a knowledge base curator for an Obsidian wiki vault.
Your job: read a raw note and output structured wiki entries.

EXISTING WIKI ENTRIES (prefer linking to these):
{existing_sample}

RAW FILE: {filename}
---
{snippet}
---

OUTPUT INSTRUCTIONS:
- Create 1-3 wiki entries: always a source entry, plus entity/concept entries if warranted
- Source entry → wiki/sources/
- People, companies, tools → wiki/entities/
- Ideas, frameworks, strategies → wiki/concepts/
- Every entry MUST have at least 2 [[wikilinks]] using Title Case
- Prefer [[wikilinks]] that match EXISTING entries listed above
- Be concise and factual

OUTPUT FORMAT — use this exact delimiter pattern, nothing else:

===FILE: wiki/sources/Source Name Here.md===
# Source Name Here

## Summary
2-3 sentences about what this source covers.

## Key Points
- bullet point 1
- bullet point 2

## Connections
- Related to: [[Existing Entry]]
- See also: [[Another Entry]]

## Source
{filename}

## Tags
#tag1 #tag2
===END===

===FILE: wiki/entities/Person Or Tool Name.md===
# Person Or Tool Name

## Summary
Who or what this is.

## Key Points
- key point

## Connections
- Related to: [[Concept]]
- See also: [[Source]]

## Source
{filename}

## Tags
#tag
===END===

Now process the raw file above. Output ONLY the ===FILE:...===END=== blocks.
"""


def parse_response(response: str) -> list:
    """
    Extract (rel_path, content) pairs from model output.
    Returns empty list if model output is malformed.
    """
    pattern = r'===FILE:\s*([\w/][^\n]+\.md)===\n(.*?)===END==='
    matches = re.findall(pattern, response, re.DOTALL)
    return [(m[0].strip(), m[1].strip()) for m in matches]


def write_wiki_entry(rel_path: str, content: str) -> bool:
    """
    Write a wiki entry. If file already exists, append new connections
    rather than overwriting — same rule as /second-brain-ingest skill.
    Returns True if a new file was created.
    """
    full_path = VAULT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    if full_path.exists():
        existing_text = full_path.read_text()
        # Extract wikilinks from new content not already in the file
        new_links = re.findall(r'\[\[[^\]]+\]\]', content)
        novel = [l for l in new_links if l not in existing_text]
        if novel:
            stamp = datetime.now().strftime("%Y-%m-%d")
            addition = f"\n\n## New Connections ({stamp})\n" + "\n".join(f"- {l}" for l in novel)
            if not DRY_RUN:
                full_path.write_text(existing_text + addition)
            return False   # updated, not created
        return False       # nothing new to add
    else:
        if not DRY_RUN:
            full_path.write_text(content)
        return True        # new file


def append_log(entries: list):
    """Append an ingest session summary to the log file."""
    if DRY_RUN:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n### {stamp}"]
    for filename, created_files in entries:
        lines.append(f"- **{filename}** → {len(created_files)} entries")
        for f in created_files:
            lines.append(f"  - `{f}`")
    with open(LOG_FILE, "a") as fh:
        fh.write("\n".join(lines) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # Frequency gate: skip if run too recently (launchd fires daily, script enforces 48h gap)
    if not should_run_today():
        return

    raw_files = get_raw_files()
    if not raw_files:
        print("Second Brain ingest: nothing to process.")
        record_run()   # still stamp so the 48h clock resets
        return

    existing = get_existing_wiki_stems()
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Found {len(raw_files)} raw file(s), {len(existing)} existing wiki entries")
    print(f"Model: {MODEL}\n")

    session_log = []

    for raw_file in raw_files:
        print(f"Processing: {raw_file.name}")
        content = raw_file.read_text(encoding="utf-8", errors="ignore")

        try:
            response = call_ollama(build_prompt(content, raw_file.name, existing))
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            print("  Skipping — Ollama must be running (ollama serve)")
            continue

        pairs = parse_response(response)
        if not pairs:
            print(f"  WARNING: model output had no valid ===FILE:...===END=== blocks")
            print(f"  Raw response preview: {response[:300]}")
            continue

        created_files = []
        for rel_path, md_content in pairs:
            is_new = write_wiki_entry(rel_path, md_content)
            status = "created" if is_new else "updated"
            print(f"  {'+' if is_new else '~'} [{status}] {rel_path}")
            created_files.append(rel_path)
            existing.append(Path(rel_path).stem)   # add to known entries for next file

        session_log.append((raw_file.name, created_files))

        # Move to processed/
        dest = PROCESSED / raw_file.name
        if not DRY_RUN:
            if dest.exists():
                dest = PROCESSED / f"{raw_file.stem}_{datetime.now().strftime('%H%M%S')}.md"
            shutil.move(str(raw_file), str(dest))
            print(f"  → Moved to raw/processed/")

    append_log(session_log)
    record_run()
    total = sum(len(v) for _, v in session_log)
    print(f"\nDone. {len(session_log)} file(s) processed, {total} wiki entries written.")
    if DRY_RUN:
        print("[DRY RUN] No files were actually written or moved.")


if __name__ == "__main__":
    main()
