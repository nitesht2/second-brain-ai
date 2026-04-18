#!/usr/bin/env python3
"""
Second Brain Auto-Ingest via Local LLM (Ollama)

Scans ~/SecondBrain/raw/ for unprocessed files and ingests them
using a local model (Gemma 3 / Qwen 3.5) — zero Claude Code tokens.

Supported input formats:
  .md    → markdown clips (Web Clipper output)
  .pdf   → PDF documents (text extracted via pypdf)
  .txt   → plain text, OR a YouTube URL on the first line
           (transcript fetched via youtube-transcript-api)

Open-source dependencies used by this script:
  - Ollama              (local LLM runtime)    — https://github.com/ollama/ollama
  - poppler (pdftotext) (PDF text extraction)  — https://poppler.freedesktop.org
  - pypdf               (PDF fallback)         — https://github.com/py-pdf/pypdf
  - youtube-transcript-api (YouTube transcripts) — https://github.com/jdepoix/youtube-transcript-api

Usage:
    python3 auto_ingest.py                        # normal ingest run
    python3 auto_ingest.py --dry-run              # preview only, no writes
    python3 auto_ingest.py --synthesize           # synthesize wiki/ into wiki/synthesis/
    python3 auto_ingest.py --synthesize --dry-run # preview synthesis, no writes
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


SUPPORTED_EXTENSIONS = {".md", ".pdf", ".txt"}


def get_raw_files():
    """Return all supported files in raw/ that are not inside processed/.

    Supported types:
      .md   → plain markdown (Web Clipper output)
      .pdf  → extracted as text via pypdf
      .txt  → plain text, OR a single YouTube URL (transcript is fetched)
    """
    files = []
    for p in RAW_DIR.rglob("*"):
        if not p.is_file() or "processed" in p.parts:
            continue
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
    return sorted(files)


def extract_pdf_text(pdf_path) -> str:
    """Extract all text from a PDF.

    Tries in order:
      1. pdftotext (poppler)  — industry standard, most accurate, fastest
         https://poppler.freedesktop.org  — install: `brew install poppler`
      2. pypdf (pure Python)  — fallback, no external dependency
         https://github.com/py-pdf/pypdf  — install: `pip3 install pypdf`
    """
    import shutil as _sh
    import subprocess

    # Try 1: pdftotext (preferred — industry standard, poppler-based)
    if _sh.which("pdftotext"):
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), "-"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"# {pdf_path.stem}\n\n{result.stdout}"
            else:
                print(f"  ⚠ pdftotext returned empty — falling back to pypdf")
        except Exception as e:
            print(f"  ⚠ pdftotext failed: {e} — falling back to pypdf")

    # Try 2: pypdf (pure Python fallback)
    try:
        import pypdf
    except ImportError:
        print("  ⚠ No PDF extractor available. Install either:")
        print("    brew install poppler                            (recommended)")
        print("    pip3 install --break-system-packages pypdf      (fallback)")
        return ""
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        parts = [f"# {pdf_path.stem}\n"]
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
        return "\n\n".join(parts)
    except Exception as e:
        print(f"  ⚠ PDF extraction failed: {e}")
        return ""


def extract_video_id(url: str):
    """Pull a YouTube video ID out of any common URL format."""
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[?&#]|$)',
        r'youtu\.be/([0-9A-Za-z_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def fetch_youtube_transcript(url: str) -> str:
    """Fetch a YouTube video transcript. Uses youtube-transcript-api (open-source, MIT).
    https://github.com/jdepoix/youtube-transcript-api
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("  ⚠ youtube-transcript-api not installed. Install with:")
        print("    pip3 install --break-system-packages youtube-transcript-api")
        return ""
    video_id = extract_video_id(url)
    if not video_id:
        print(f"  ⚠ Could not extract video ID from: {url}")
        return ""
    try:
        # v1.x API: instantiate, then fetch() returns FetchedTranscript (iterable of snippets)
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        body = "\n".join(snippet.text for snippet in fetched)
        return f"# YouTube Transcript\n\nSource: {url}\n\n{body}"
    except Exception as e:
        print(f"  ⚠ Transcript fetch failed for {video_id}: {e}")
        return ""


def extract_content(file_path) -> str:
    """Read file content, converting PDF and YouTube-URL txt files to markdown on the fly."""
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        return extract_pdf_text(file_path)

    if suffix == ".txt":
        raw = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if "youtube.com/watch" in raw or "youtu.be/" in raw:
            # First line is treated as the URL
            url = raw.splitlines()[0].strip()
            return fetch_youtube_transcript(url)
        return raw

    return ""


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


# ── Synthesis ─────────────────────────────────────────────────────────────────

def collect_wiki_digests() -> list:
    """Read all wiki entries (entities, concepts, sources) and return digest dicts.

    Each digest contains:
      stem    — filename without .md (used to match cluster output)
      path    — absolute Path to the file
      summary — first 300 chars of file content (enough to cluster without full text)
    """
    digests = []
    for folder in ("entities", "concepts", "sources"):
        for p in sorted((WIKI_DIR / folder).glob("*.md")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            digests.append({
                "stem": p.stem,
                "path": p,
                "summary": text[:300].replace("\n", " "),
            })
    return digests


def build_cluster_prompt(digests: list) -> str:
    """Ask Ollama to group wiki entries into 3-6 named theme clusters."""
    entries_block = "\n".join(
        f"{i+1}. [{d['stem']}] {d['summary']}"
        for i, d in enumerate(digests)
    )
    return f"""You are organizing a personal knowledge base into thematic clusters.

Below are {len(digests)} wiki entries with their names and a short preview.
Group them into 3-6 named clusters based on shared themes.

ENTRIES:
{entries_block}

OUTPUT FORMAT — use this exact pattern, nothing else:

===CLUSTER: Theme Name===
Entry Stem 1, Entry Stem 2, Entry Stem 3
===END===

Rules:
- Every entry must appear in exactly one cluster
- Cluster names should be 2-4 words, Title Case
- Use the exact stem names (inside [ ] above) — no paraphrasing
- Minimum 3 entries per cluster; merge small groups into the nearest theme
- Output ONLY the ===CLUSTER:...===END=== blocks
"""


def parse_clusters(response: str) -> dict:
    """Extract cluster_name → [entry stems] from Ollama cluster response.

    Strips any surrounding brackets the model may echo (e.g. [Anthropic] → Anthropic).
    """
    pattern = r'===CLUSTER:\s*([^\n]+)===\n(.*?)===END==='
    matches = re.findall(pattern, response, re.DOTALL)
    clusters = {}
    for name, body in matches:
        raw_stems = re.split(r'[,\n]+', body)
        stems = [s.strip().strip('[]').strip() for s in raw_stems if s.strip().strip('[]').strip()]
        if stems:
            clusters[name.strip()] = stems
    return clusters


def _norm(s: str) -> str:
    """Normalize a stem for fuzzy matching: lowercase, strip all non-alphanumeric chars."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def build_synthesis_prompt(cluster_name: str, entries_text: str, all_stems: list) -> str:
    """Build the synthesis prompt for a single theme cluster."""
    all_entries_ref = "\n".join(f"  - [[{s}]]" for s in all_stems[:80])
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""You are synthesizing insights from a personal knowledge base.

THEME CLUSTER: {cluster_name}

WIKI ENTRIES IN THIS CLUSTER:
---
{entries_text}
---

ALL KNOWN WIKI ENTRIES (use for [[wikilinks]]):
{all_entries_ref}

Your task: find what these entries reveal TOGETHER that none states alone.
Look for shared patterns, unexpected contradictions, and a non-obvious key insight.

OUTPUT FORMAT — use this exact pattern:

===FILE: wiki/synthesis/Synthesis - {cluster_name}.md===
# Synthesis: {cluster_name}

## Overview
2-3 sentences on why these entries cluster together and what domain they cover.

## Shared Patterns
- Pattern 1 (seen in [[Entry A]] and [[Entry B]])
- Pattern 2 (seen in [[Entry C]], [[Entry D]], [[Entry E]])

## Contradictions Found
- [[Entry A]] emphasizes X, while [[Entry B]] recommends Y — resolution: ...

## Key Insight
One paragraph: the non-obvious conclusion that ONLY emerges by reading these entries together.

## Actionable Takeaways
- Concrete action 1
- Concrete action 2

## Sources Synthesized
- [[{cluster_name.replace(' ', '-')}]]

## Generated
{today}
===END===

Output ONLY the ===FILE:...===END=== block. Use real [[wikilinks]] from the entries above.
"""


def run_synthesis():
    """Two-phase synthesis: cluster all wiki entries, then synthesize each cluster."""
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Starting wiki synthesis...")
    print(f"Model: {MODEL}\n")

    digests = collect_wiki_digests()
    if not digests:
        print("No wiki entries found. Ingest some raw files first.")
        return

    all_stems = [d["stem"] for d in digests]
    print(f"Phase 1: Clustering {len(digests)} wiki entries...")

    try:
        cluster_response = call_ollama(build_cluster_prompt(digests))
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        print("  Ollama must be running (open Ollama.app)")
        return

    clusters = parse_clusters(cluster_response)
    if not clusters:
        print("  WARNING: Model returned no valid ===CLUSTER:...===END=== blocks")
        print(f"  Raw response preview: {cluster_response[:400]}")
        return

    print(f"  Found {len(clusters)} cluster(s):\n")
    for name, stems in clusters.items():
        print(f"  [{name}] ({len(stems)} entries): {', '.join(stems[:4])}{'...' if len(stems) > 4 else ''}")
    print()

    # Phase 2: synthesize each cluster
    (WIKI_DIR / "synthesis").mkdir(parents=True, exist_ok=True)
    created_total = 0

    print("Phase 2: Synthesizing each cluster...\n")
    for cluster_name, stems in clusters.items():
        if len(stems) < 3:
            print(f"  Skipping [{cluster_name}] — only {len(stems)} entries (need 3+)")
            continue

        # Collect full content for entries in this cluster (fuzzy match on stem)
        parts = []
        matched_stems = []
        stem_map_norm = {_norm(d["stem"]): d for d in digests}
        for stem in stems:
            hit = stem_map_norm.get(_norm(stem))
            if hit:
                text = hit["path"].read_text(encoding="utf-8", errors="ignore")
                parts.append(f"### {hit['stem']}\n{text[:1200]}")
                matched_stems.append(hit["stem"])

        if len(matched_stems) < 3:
            print(f"  Skipping [{cluster_name}] — fewer than 3 entries matched on disk")
            continue

        entries_text = "\n\n".join(parts)
        print(f"  Synthesizing [{cluster_name}] from {len(matched_stems)} entries...")

        try:
            synthesis_response = call_ollama(
                build_synthesis_prompt(cluster_name, entries_text, all_stems)
            )
        except RuntimeError as e:
            print(f"    ERROR: {e}")
            continue

        pairs = parse_response(synthesis_response)
        if not pairs:
            print(f"    WARNING: No valid ===FILE:...===END=== in response")
            print(f"    Preview: {synthesis_response[:300]}")
            continue

        for rel_path, md_content in pairs:
            is_new = write_wiki_entry(rel_path, md_content)
            status = "created" if is_new else "updated"
            print(f"    {'+' if is_new else '~'} [{status}] {rel_path}")
            if is_new:
                created_total += 1

    print(f"\nSynthesis done. {created_total} new synthesis entries created.")
    if DRY_RUN:
        print("[DRY RUN] No files were actually written.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Synthesis mode — bypass ingest entirely
    if "--synthesize" in sys.argv:
        run_synthesis()
        return

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
        kind = {
            ".md": "markdown",
            ".pdf": "PDF",
            ".txt": "text/YouTube URL",
        }.get(raw_file.suffix.lower(), "unknown")
        print(f"Processing [{kind}]: {raw_file.name}")
        content = extract_content(raw_file)
        if not content.strip():
            print("  ⚠ No content extracted — skipping.")
            continue

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

    # Auto-run synthesis after every ingest so wiki/synthesis/ stays current
    if session_log:
        print("\n─── Auto-synthesis starting ───")
        run_synthesis()


if __name__ == "__main__":
    main()
