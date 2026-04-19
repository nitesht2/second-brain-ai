#!/usr/bin/env python3
"""
Second Brain Auto-Ingest

Scans ~/SecondBrain/raw/ for unprocessed files and ingests them
using Ollama (free, local) or Kimi K2 API (paid, better quality).

Provider selection (default: ollama):
    export SECOND_BRAIN_PROVIDER=kimi      # use Kimi K2, auto-fallback to Gemma 3
    export SECOND_BRAIN_PROVIDER=ollama    # local Gemma 3 only (default)

Supported input formats:
  .md    → markdown clips (Web Clipper output) — best for social media (TikTok, Instagram, Twitter)
  .pdf   → PDF documents (text extracted via pypdf)
  .txt   → plain text, OR a YouTube URL on the first line
           (transcript fetched via youtube-transcript-api)

Open-source dependencies used by this script:
  - Ollama              (local LLM runtime)    — https://github.com/ollama/ollama
  - poppler (pdftotext) (PDF text extraction)  — https://poppler.freedesktop.org
  - pypdf               (PDF fallback)         — https://github.com/py-pdf/pypdf
  - youtube-transcript-api (YouTube transcripts) — https://github.com/jdepoix/youtube-transcript-api

Usage:
    python3 auto_ingest.py                               # normal ingest run
    python3 auto_ingest.py --dry-run                     # preview only, no writes
    python3 auto_ingest.py --synthesize                  # synthesize wiki/ into wiki/synthesis/
    python3 auto_ingest.py --synthesize --dry-run        # preview synthesis, no writes
    python3 auto_ingest.py --synthesize --force-synthesis # regenerate ALL clusters (ignore incremental guard)
    python3 auto_ingest.py --save <URL>                  # download TikTok/Instagram, transcribe, save to raw/
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
BRAND_DIR   = VAULT / "brand"  # Brand Foundation (voice, style, banned words, positioning, audience)
LOG_FILE    = VAULT / "outputs" / "ingest-log.md"

OLLAMA_URL      = "http://127.0.0.1:11434/api/generate"
MODEL           = "gemma3:4b"         # reliable structured output; qwen3.5:* also works (answer is in 'thinking' field)
TEMPERATURE     = 0.2                 # low = more consistent structure
MAX_TOKENS      = 3000
RAW_CHUNK       = 3500                # chars fed to model per file
LAST_RUN_FILE   = VAULT / "outputs" / ".last_ingest_run"
MIN_HOURS       = 48                  # skip if last run was less than this many hours ago

# ── Provider config ───────────────────────────────────────────────────────────
# Switch between local Ollama (free) and Kimi K2 API (~$0.005/run, better quality)
#
#   To use Kimi:
#     export SECOND_BRAIN_PROVIDER=kimi
#     export KIMI_API_KEY=your_key_here
#
#   To use Ollama (default, free):
#     export SECOND_BRAIN_PROVIDER=ollama   (or just don't set it)

PROVIDER        = os.environ.get("SECOND_BRAIN_PROVIDER", "ollama").lower()
KIMI_API_KEY    = os.environ.get("KIMI_API_KEY", "")
KIMI_MODEL      = "kimi-k2-0905-preview"
KIMI_BASE_URL   = "https://api.moonshot.ai/v1/chat/completions"

# Kimi K2 pricing per 1M tokens (as of 2026)
KIMI_INPUT_PRICE_PER_M  = 0.15
KIMI_OUTPUT_PRICE_PER_M = 2.50

# Hard cost cap per ingest run. Exceeding this halts the run and fires
# a macOS notification. A typical run costs ~$0.04-$0.10, so $1.00 is a
# ~20x safety margin that still prevents runaway bugs (e.g. 100 clips,
# huge prompts, retry loops). Override with env var COST_CAP_USD.
COST_CAP_USD         = float(os.environ.get("COST_CAP_USD", "1.00"))

# Monthly cumulative cap. Once crossed, the pipeline auto-downgrades to
# free Ollama/Gemma 3 for the rest of the calendar month so clips still
# get processed — you just stop paying. Resets on the 1st of each month.
COST_CAP_MONTHLY_USD = float(os.environ.get("COST_CAP_MONTHLY_USD", "5.00"))

# Running tallies for the current ingest session
_SESSION_TOKENS = {"input": 0, "output": 0, "calls": 0}


class CostCapExceeded(Exception):
    """Raised when Kimi session cost crosses COST_CAP_USD. Halts the run."""


def _session_cost() -> float:
    """Return USD cost of Kimi API calls so far this session."""
    return (
        _SESSION_TOKENS["input"]  / 1_000_000 * KIMI_INPUT_PRICE_PER_M +
        _SESSION_TOKENS["output"] / 1_000_000 * KIMI_OUTPUT_PRICE_PER_M
    )


def _monthly_spend() -> float:
    """Parse outputs/cost-log.md and sum costs from the current calendar month.

    The log format is: | YYYY-MM-DD HH:MM | calls | in | out | $0.0042 |
    We extract the date prefix and dollar amount from each row.
    """
    log = VAULT / "outputs" / "cost-log.md"
    if not log.exists():
        return 0.0
    month_prefix = datetime.now().strftime("%Y-%m")
    total = 0.0
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.startswith(f"| {month_prefix}"):
            continue
        m = re.search(r'\$([\d.]+)\s*\|', line)
        if m:
            try:
                total += float(m.group(1))
            except ValueError:
                continue
    return total


def _notify_macos(title: str, message: str):
    """Fire a native macOS notification (no deps, uses osascript)."""
    try:
        import subprocess
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}" sound name "Basso"'],
            timeout=5, capture_output=True,
        )
    except Exception:
        pass  # notifications are best-effort

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


def is_already_ingested(video_id: str) -> bool:
    """Return True if a YouTube video ID already exists in any wiki/sources/ entry.

    Prevents duplicate wiki entries when the same video is captured via both
    the bookmarklet (.txt) and Obsidian Web Clipper (.md).
    """
    sources_dir = WIKI_DIR / "sources"
    if not sources_dir.exists():
        return False
    for p in sources_dir.glob("*.md"):
        try:
            if video_id in p.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False


def extract_content(file_path) -> str:
    """Read file content, converting PDF and YouTube-URL txt files to markdown on the fly.

    For .md files from Obsidian Web Clipper: detects YouTube URLs in YAML frontmatter
    (source: field) and automatically fetches the full transcript.

    For TikTok, Instagram, and Twitter — use Obsidian Web Clipper instead.
    These platforms block programmatic access. Web Clipper reads what's in
    your browser session and saves it as .md automatically.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".md":
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        # Check for YAML frontmatter with a YouTube source URL (Obsidian Web Clipper format)
        fm_match = re.search(r'^---\s*\n(.*?)\n---', raw, re.DOTALL)
        if fm_match:
            fm_block = fm_match.group(1)
            source_match = re.search(
                r'^source:\s*["\']?(https?://[^\s"\']+)["\']?',
                fm_block,
                re.MULTILINE,
            )
            if source_match:
                url = source_match.group(1).strip()

                # YouTube — fetch transcript via API (no browser needed)
                video_id = extract_video_id(url)
                if video_id:
                    if is_already_ingested(video_id):
                        print(f"  ⚠ Already in wiki (video ID {video_id}) — skipping duplicate.")
                        return ""
                    print(f"  ▶ YouTube URL detected in frontmatter — fetching transcript...")
                    transcript = fetch_youtube_transcript(url)
                    if transcript:
                        body = raw[fm_match.end():].strip()
                        return f"{body}\n\n{transcript}" if body else transcript

                # TikTok / Instagram — Web Clipper already captured description,
                # hashtags, and caption. Use that directly. For full transcript,
                # run: python3 auto_ingest.py --save <URL>
                elif any(d in url for d in ("tiktok.com", "instagram.com", "instagr.am")):
                    print(f"  ▶ TikTok/Instagram clip detected — using Web Clipper content.")
        # Fallback: return full file as-is (articles, notes, non-video clips)
        return raw

    if suffix == ".pdf":
        return extract_pdf_text(file_path)

    if suffix == ".txt":
        raw = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if "youtube.com/watch" in raw or "youtu.be/" in raw:
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


def call_kimi(prompt: str) -> str:
    """Call Kimi K2 API (OpenAI-compatible). ~$0.005 per ingest run, better quality than Gemma 3."""
    if not KIMI_API_KEY:
        raise RuntimeError("KIMI_API_KEY not set. Run: export KIMI_API_KEY=your_key")

    payload = json.dumps({
        "model": KIMI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }).encode()

    req = urllib.request.Request(
        KIMI_BASE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {KIMI_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
            # Track usage for cost reporting
            usage = body.get("usage", {})
            _SESSION_TOKENS["input"]  += usage.get("prompt_tokens", 0)
            _SESSION_TOKENS["output"] += usage.get("completion_tokens", 0)
            _SESSION_TOKENS["calls"]  += 1

            # Hard cost cap — halt the run if we cross the threshold
            cost_so_far = _session_cost()
            if cost_so_far > COST_CAP_USD:
                raise CostCapExceeded(
                    f"Kimi session cost ${cost_so_far:.4f} exceeded cap ${COST_CAP_USD:.2f} "
                    f"after {_SESSION_TOKENS['calls']} calls"
                )
            return body["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise RuntimeError(f"Kimi API not reachable: {e}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Kimi API response: {e}")


def call_llm(prompt: str) -> str:
    """Route to Kimi or Ollama based on SECOND_BRAIN_PROVIDER env var.

    If SECOND_BRAIN_PROVIDER=kimi and the Kimi call fails for any reason,
    automatically falls back to local Ollama (Gemma 3) so ingest never
    silently fails just because the API is down.
    """
    if PROVIDER == "kimi":
        try:
            return call_kimi(prompt)
        except CostCapExceeded:
            # Don't fall back — the whole point of the cap is to STOP.
            # Bubble up so the main loop can halt and notify the user.
            raise
        except RuntimeError as e:
            print(f"  ⚠ Kimi failed ({e}) — falling back to Ollama/Gemma 3")
            return call_ollama(prompt)
    return call_ollama(prompt)


def load_brand_foundation() -> str:
    """Read all files in brand/ and concatenate into a single string.

    Brand Foundation (BF) is the static layer that tells agents how the human
    sounds before producing anything. Agents read this but never modify it.

    Returns empty string if brand/ doesn't exist (graceful — BF is optional).
    """
    if not BRAND_DIR.exists():
        return ""
    parts = []
    for p in sorted(BRAND_DIR.glob("*.md")):
        try:
            parts.append(f"### {p.stem.replace('-', ' ').title()}\n\n{p.read_text(encoding='utf-8').strip()}")
        except OSError:
            continue
    if not parts:
        return ""
    return "\n\n".join(parts)


def build_prompt(content: str, filename: str, existing: list) -> str:
    """Build the ingest prompt, injecting existing wiki names for wikilinks."""
    existing_sample = "\n".join(f"  - [[{e}]]" for e in existing[:60])
    snippet = content[:RAW_CHUNK]
    if len(content) > RAW_CHUNK:
        snippet += "\n... [truncated]"

    brand = load_brand_foundation()
    brand_section = f"""
BRAND FOUNDATION (read before writing anything — this is how the human sounds):
{brand}
""" if brand else ""

    return f"""You are a knowledge base curator for an Obsidian wiki vault.
Your job: read a raw note and output structured wiki entries.
{brand_section}
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
- Follow the BRAND FOUNDATION above: no em dashes, no banned phrases, match the voice rules.
- Add a `confidence:` frontmatter field with value high/medium/low/uncertain based on source quality.
- Include a `## Counter-arguments` section naming what the source might be missing or what a skeptic would say.

OUTPUT FORMAT — use this exact delimiter pattern, nothing else:

===FILE: wiki/sources/Source Name Here.md===
---
confidence: high
explored: false
---
# Source Name Here

## Summary
2-3 sentences about what this source covers.

## Key Points
- bullet point 1
- bullet point 2

## Counter-arguments
- What the source might be missing
- What a skeptic would push back on

## Connections
- Related to: [[Existing Entry]]
- See also: [[Another Entry]]

## Source
{filename}

## Tags
#tag1 #tag2
===END===

===FILE: wiki/entities/Person Or Tool Name.md===
---
confidence: high
explored: false
---
# Person Or Tool Name

## Summary
Who or what this is.

## Key Points
- key point

## Counter-arguments
- Known limitations or critiques of this entity/tool

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


def append_cost_log():
    """Write token usage and $ cost to outputs/cost-log.md for this session.

    Only runs when provider=kimi (Ollama is free). Appends one row per run.
    """
    if PROVIDER != "kimi" or DRY_RUN or _SESSION_TOKENS["calls"] == 0:
        return
    in_tok  = _SESSION_TOKENS["input"]
    out_tok = _SESSION_TOKENS["output"]
    cost = (in_tok / 1_000_000 * KIMI_INPUT_PRICE_PER_M) + \
           (out_tok / 1_000_000 * KIMI_OUTPUT_PRICE_PER_M)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log = VAULT / "outputs" / "cost-log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(
            "# Kimi K2 Cost Log\n\n"
            "| Date | Calls | Input tokens | Output tokens | Cost (USD) |\n"
            "|---|---|---|---|---|\n"
        )
    with open(log, "a") as fh:
        fh.write(f"| {stamp} | {_SESSION_TOKENS['calls']} | {in_tok:,} | {out_tok:,} | ${cost:.4f} |\n")
    print(f"  💰 Kimi cost this run: ${cost:.4f} ({in_tok:,} in + {out_tok:,} out across {_SESSION_TOKENS['calls']} calls)")


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


def needs_resynthesis(cluster_name: str, entry_paths: list) -> bool:
    """Return True if the synthesis file is missing OR any cluster entry was
    modified after the synthesis file was last written.

    This is the core of incremental synthesis: skip clusters where nothing
    changed since last run. Typical savings at steady state are 3-5x because
    most clusters don't change day-to-day.

    Matches the filename produced by build_synthesis_prompt():
        wiki/synthesis/Synthesis - {cluster_name}.md
    """
    synth_file = WIKI_DIR / "synthesis" / f"Synthesis - {cluster_name}.md"
    if not synth_file.exists():
        return True  # never synthesized → do it
    synth_mtime = synth_file.stat().st_mtime
    for p in entry_paths:
        try:
            if p.stat().st_mtime > synth_mtime:
                return True
        except OSError:
            return True  # path gone? safer to regenerate
    return False


def build_synthesis_prompt(cluster_name: str, entries_text: str, all_stems: list) -> str:
    """Build the synthesis prompt for a single theme cluster."""
    all_entries_ref = "\n".join(f"  - [[{s}]]" for s in all_stems[:80])
    today = datetime.now().strftime("%Y-%m-%d")
    brand = load_brand_foundation()
    brand_section = f"""
BRAND FOUNDATION (read before writing — match this voice, follow these rules):
{brand}
""" if brand else ""
    return f"""You are synthesizing insights from a personal knowledge base.
{brand_section}
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
    provider_label = f"Kimi K2 → Gemma 3 fallback" if PROVIDER == "kimi" else f"Ollama ({MODEL})"
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Starting wiki synthesis...")
    print(f"Provider: {provider_label}\n")

    digests = collect_wiki_digests()
    if not digests:
        print("No wiki entries found. Ingest some raw files first.")
        return

    all_stems = [d["stem"] for d in digests]
    print(f"Phase 1: Clustering {len(digests)} wiki entries...")

    try:
        cluster_response = call_llm(build_cluster_prompt(digests))
    except CostCapExceeded as e:
        print(f"\n  🛑 COST CAP HIT: {e}")
        _notify_macos("Second Brain: cost cap hit",
                      f"Synthesis halted at ${_session_cost():.2f}.")
        return
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        print("  Make sure Ollama is running (open Ollama.app)")
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

    force = "--force-synthesis" in sys.argv
    skipped_unchanged = 0

    print("Phase 2: Synthesizing each cluster...\n")
    for cluster_name, stems in clusters.items():
        if len(stems) < 3:
            print(f"  Skipping [{cluster_name}] — only {len(stems)} entries (need 3+)")
            continue

        # Collect full content for entries in this cluster (fuzzy match on stem)
        parts = []
        matched_stems = []
        matched_paths = []
        stem_map_norm = {_norm(d["stem"]): d for d in digests}
        for stem in stems:
            hit = stem_map_norm.get(_norm(stem))
            if hit:
                text = hit["path"].read_text(encoding="utf-8", errors="ignore")
                parts.append(f"### {hit['stem']}\n{text[:1200]}")
                matched_stems.append(hit["stem"])
                matched_paths.append(hit["path"])

        if len(matched_stems) < 3:
            print(f"  Skipping [{cluster_name}] — fewer than 3 entries matched on disk")
            continue

        # Incremental guard: skip if no entry has changed since last synthesis
        if not force and not needs_resynthesis(cluster_name, matched_paths):
            print(f"  ⏭  Skipping [{cluster_name}] — unchanged since last synthesis")
            skipped_unchanged += 1
            continue

        entries_text = "\n\n".join(parts)
        print(f"  Synthesizing [{cluster_name}] from {len(matched_stems)} entries...")

        try:
            synthesis_response = call_llm(
                build_synthesis_prompt(cluster_name, entries_text, all_stems)
            )
        except CostCapExceeded as e:
            print(f"\n    🛑 COST CAP HIT: {e}")
            _notify_macos("Second Brain: cost cap hit",
                          f"Synthesis stopped mid-run at ${_session_cost():.2f}.")
            return
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

    print(f"\nSynthesis done. {created_total} new synthesis entries created, "
          f"{skipped_unchanged} cluster(s) skipped as unchanged.")
    if skipped_unchanged and not force:
        print(f"  (Use --force-synthesis to regenerate all clusters)")
    if DRY_RUN:
        print("[DRY RUN] No files were actually written.")


# ── Index ─────────────────────────────────────────────────────────────────────

def update_wiki_index():
    """Regenerate wiki/index.md as a full table of contents of the vault.

    Scans all four wiki folders and writes a clean index with entry counts.
    Always overwrites — index is a derived artifact, not a hand-edited file.
    """
    folders = [
        ("entities",  "Entities",  "people, companies, tools"),
        ("concepts",  "Concepts",  "ideas, frameworks, strategies"),
        ("sources",   "Sources",   "articles, videos, PDFs"),
        ("synthesis", "Synthesis", "cross-topic insights"),
    ]

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Wiki Index",
        f"*Last updated: {stamp}*",
        "",
        "> Auto-generated by auto_ingest.py — do not edit by hand.",
        "",
    ]

    total = 0
    for folder, label, desc in folders:
        entries = sorted((WIKI_DIR / folder).glob("*.md"), key=lambda p: p.stem.lower())
        count = len(entries)
        total += count
        lines.append(f"## {label} ({count})")
        lines.append(f"*{desc}*")
        lines.append("")
        if entries:
            for p in entries:
                lines.append(f"- [[{p.stem}]]")
        else:
            lines.append("*None yet — ingest some files to populate this section.*")
        lines.append("")

    lines.insert(4, f"**Total entries: {total}**")
    lines.insert(5, "")

    index_path = WIKI_DIR / "index.md"
    if not DRY_RUN:
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  ✓ wiki/index.md updated ({total} entries)")
    else:
        print(f"  [DRY RUN] wiki/index.md would list {total} entries")


# ── Main ──────────────────────────────────────────────────────────────────────

def _check_monthly_cap():
    """If this month's Kimi spend already exceeds COST_CAP_MONTHLY_USD,
    auto-downgrade the provider to Ollama for this run and notify the user.

    Mutates the module-level PROVIDER so all subsequent call_llm() calls
    route to free Ollama instead of paid Kimi. Clips still get processed —
    you just stop paying until the next month rolls over.
    """
    global PROVIDER
    if PROVIDER != "kimi":
        return
    spent = _monthly_spend()
    if spent >= COST_CAP_MONTHLY_USD:
        month = datetime.now().strftime("%B")
        print(f"\n  💰 Monthly cap reached: ${spent:.2f} spent on Kimi in {month} "
              f"(cap: ${COST_CAP_MONTHLY_USD:.2f})")
        print(f"     Auto-downgrading to free Ollama/Gemma 3 for the rest of {month}.")
        _notify_macos(
            f"Second Brain: {month} budget used",
            f"${spent:.2f} spent. Switched to free Ollama until {month[:3]} 1st.",
        )
        PROVIDER = "ollama"
    elif spent > 0:
        print(f"  💰 Kimi spend this month: ${spent:.2f} / ${COST_CAP_MONTHLY_USD:.2f}")


def main():
    # Synthesis mode — bypass ingest entirely
    if "--synthesize" in sys.argv:
        _check_monthly_cap()
        run_synthesis()
        return

    # Save mode — download a social media URL and transcribe it into raw/
    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 >= len(sys.argv):
            print("Usage: python3 auto_ingest.py --save <TikTok or Instagram URL>")
            return
        url = sys.argv[idx + 1]
        try:
            from social_downloader import download_and_transcribe
        except ImportError:
            # Try loading from vault directory
            import importlib.util, pathlib
            spec = importlib.util.spec_from_file_location(
                "social_downloader",
                pathlib.Path(__file__).parent / "social_downloader.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            download_and_transcribe = mod.download_and_transcribe
        download_and_transcribe(url)
        return

    PROCESSED.mkdir(parents=True, exist_ok=True)

    # Frequency gate: skip if run too recently (launchd fires daily, script enforces 48h gap)
    if not should_run_today():
        return

    # Budget gate: if month's Kimi spend is over the cap, switch to free Ollama
    _check_monthly_cap()

    raw_files = get_raw_files()
    if not raw_files:
        print("Second Brain ingest: nothing to process.")
        record_run()   # still stamp so the 48h clock resets
        update_wiki_index()  # keep index current even with no new files
        return

    existing = get_existing_wiki_stems()
    provider_label = f"Kimi K2 → Gemma 3 fallback" if PROVIDER == "kimi" else f"Ollama ({MODEL})"
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Found {len(raw_files)} raw file(s), {len(existing)} existing wiki entries")
    print(f"Provider: {provider_label}\n")

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
            response = call_llm(build_prompt(content, raw_file.name, existing))
        except CostCapExceeded as e:
            print(f"\n  🛑 COST CAP HIT: {e}")
            print(f"  Halting run. Unprocessed files remain in raw/ for next session.")
            _notify_macos(
                "Second Brain: cost cap hit",
                f"Kimi cost ${_session_cost():.2f} > ${COST_CAP_USD:.2f}. Run stopped.",
            )
            append_cost_log()
            return
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            print("  Skipping — make sure Ollama is running (ollama serve)")
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

    # Always regenerate index so it reflects current vault state
    print("\n─── Updating wiki/index.md ───")
    update_wiki_index()

    # Log token usage + $ cost (Kimi only; Ollama is free)
    append_cost_log()


if __name__ == "__main__":
    main()
