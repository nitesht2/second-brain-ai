#!/usr/bin/env python3
"""
Weekly Review Prep Script for Second Brain

Generates a review brief for the human's 20-minute Sunday session:
1. Picks 3 random notes from wiki/concepts/ not reviewed in 30+ days
2. Flags notes with explored=false and confidence=low
3. Checks raw/ backlog count
4. Outputs a markdown review brief to outputs/weekly-review-YYYY-MM-DD.md

Usage: python3 weekly_review.py
"""

import json
import random
import os
import re
import sys
from pathlib import Path
from datetime import datetime, date

VAULT = Path(os.environ.get(
    "SECOND_BRAIN_PATH",
    str(Path.home() / "SecondBrain"),
))
WIKI_DIR = VAULT / "wiki"
RAW_DIR = VAULT / "raw"
OUTPUT_DIR = VAULT / "outputs"
REVIEWED_FILE = VAULT / "outputs" / ".weekly_reviewed.json"

def load_reviewed():
    if REVIEWED_FILE.exists():
        return json.loads(REVIEWED_FILE.read_text())
    return {}

def save_reviewed(data):
    REVIEWED_FILE.parent.mkdir(parents=True, exist_ok=True)
    REVIEWED_FILE.write_text(json.dumps(data, indent=2))

def get_concept_files():
    concepts_dir = WIKI_DIR / "concepts"
    if not concepts_dir.exists():
        return []
    return list(concepts_dir.glob("*.md"))

def get_frontmatter_field(content, field):
    """Extract a frontmatter field value."""
    match = re.search(rf'^{field}:\s*(.+)', content, re.MULTILINE)
    return match.group(1).strip() if match else None

def days_since_reviewed(filename, reviewed_data):
    last = reviewed_data.get(filename)
    if not last:
        return 999
    last_date = date.fromisoformat(last)
    return (date.today() - last_date).days

def pick_random_notes(concept_files, reviewed_data, count=3):
    """Pick random notes not reviewed in 30+ days, prioritizing oldest."""
    candidates = []
    for f in concept_files:
        days = days_since_reviewed(f.name, reviewed_data)
        if days >= 30:
            candidates.append((f, days))

    # Sort by days since reviewed (oldest first), then shuffle for variety
    candidates.sort(key=lambda x: -x[1])
    # Take top candidates but randomize which ones
    if len(candidates) > count:
        # Pick from top 10 oldest, randomize
        pool = candidates[:10]
        random.shuffle(pool)
        selected = pool[:count]
    else:
        selected = candidates

    return selected

def flag_low_confidence_notes(concept_files):
    """Find notes with explored=false AND confidence=low."""
    flagged = []
    for f in concept_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        explored_match = re.search(r'^explored:\s*(.+)', content, re.MULTILINE)
        confidence_match = re.search(r'^confidence:\s*(.+)', content, re.MULTILINE)
        has_why_matters = '## Why It Matters' in content
        has_counter = '## Counter-arguments' in content

        explored = explored_match.group(1).strip().lower() == 'false' if explored_match else True
        confidence = confidence_match.group(1).strip().lower() if confidence_match else 'high'

        issues = []
        if explored and confidence == 'low':
            issues.append("explored=false + confidence=low")
        if not has_why_matters:
            issues.append("missing Why It Matters")
        if not has_counter:
            issues.append("missing Counter-arguments")

        if issues:
            flagged.append((f, issues))

    return flagged

def count_raw_backlog():
    """Count unprocessed files in raw/."""
    count = 0
    if not RAW_DIR.exists():
        return 0
    for p in RAW_DIR.rglob("*"):
        if p.is_file() and "processed" not in p.parts:
            count += 1
    return count

def generate_review_brief():
    today = date.today().isoformat()
    reviewed = load_reviewed()

    concept_files = get_concept_files()
    random_notes = pick_random_notes(concept_files, reviewed)
    flagged_notes = flag_low_confidence_notes(concept_files)
    backlog = count_raw_backlog()

    lines = []
    lines.append(f"# Weekly Review — {today}")
    lines.append("")
    lines.append("## 3 Random Notes to Review")
    lines.append("")

    if random_notes:
        for f, days in random_notes:
            lines.append(f"- [[{f.stem}]] (not reviewed in {days} days)")
    else:
        lines.append("- No notes pending review. Good.")

    lines.append("")
    lines.append("## Flagged Notes (Issues)")
    lines.append("")

    if flagged_notes:
        for f, issues in flagged_notes:
            lines.append(f"- [[{f.stem}]]: {', '.join(issues)}")
    else:
        lines.append("- All notes pass quality checks.")

    lines.append("")
    lines.append(f"## Raw Backlog: {backlog} files")
    lines.append("")

    if backlog > 50:
        lines.append("⚠️ BACKLOG CRITICAL. Cleanup session required.")
    elif backlog > 20:
        lines.append("Note: Backlog building. Process within 2 days.")
    else:
        lines.append("Backlog at healthy level.")

    lines.append("")
    lines.append("## Action Items")
    lines.append("- [ ] Review 3 random notes in Obsidian graph view")
    lines.append("- [ ] Ask: what does this connect to? Is this still true?")
    lines.append("- [ ] Mark reviewed notes as explored: true in frontmatter")
    lines.append("- [ ] Prune or merge any low-quality agent-generated notes")
    lines.append("- [ ] Check synthesis/ for cross-topic patterns")
    lines.append("")
    lines.append("## How to Mark Notes Reviewed")
    lines.append("After reviewing a note, update its frontmatter:")
    lines.append("```")
    lines.append("explored: true")
    lines.append("```")

    brief = "\n".join(lines)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"weekly-review-{today}.md"
    output_file.write_text(brief, encoding="utf-8")

    # Update reviewed timestamps for the notes we suggested
    for f, _ in random_notes:
        reviewed[f.name] = today
    save_reviewed(reviewed)

    print(f"Weekly review brief written: {output_file}")
    print(f"  Suggested notes: {len(random_notes)}")
    print(f"  Flagged notes: {len(flagged_notes)}")
    print(f"  Raw backlog: {backlog}")

if __name__ == "__main__":
    generate_review_brief()
