#!/usr/bin/env python3
"""sb_book_ingest.py — turn a book into one synthesis, not 77 fragments.

The normal ingest path chunks at 3,500 words and writes wiki pages per chunk.
That sizing came from a small-context provider, and for a book it produces
dozens of disconnected source pages: 77 shards of Security Analysis is noise,
not knowledge. This does a map-reduce instead.

  map     large chunks (25k words, well inside Claude Code's context) are read
          for claims, frameworks and examples. Notes only, no wiki writes.
  reduce  one final pass reads the accumulated notes and writes ONE synthesis
          page, a few concept pages for genuinely new ideas, and ONE candidate
          decision. The per-chunk notes are kept as an audit trail, not ingested.

Usage:
    sb_book_ingest.py <book.epub|.pdf|.txt|.md> [--chunk-words N] [--dry-run]

Env: SB_VAULT (default /root/SecondBrain), SB_CLAUDE (default /usr/local/bin/claude)
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VAULT = Path(os.environ.get("SB_VAULT", "/root/SecondBrain"))
CLAUDE = os.environ.get("SB_CLAUDE", "/usr/local/bin/claude")
NOTES_DIR = VAULT / "outputs" / "book-notes"
CHUNK_WORDS = 25_000        # ~33k tokens, comfortably inside one pass
MAP_TIMEOUT = 900
REDUCE_TIMEOUT = 1800


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── text extraction ────────────────────────────────────────────────────────
def extract(path: Path) -> str:
    """Plain text from anything markitdown reads (epub, pdf, docx, html, txt).

    markitdown is already this project's converter in doc2md.py, and it keeps
    paragraph structure that a hand-rolled tag-stripper loses: on Security
    Analysis it yields 5,509 paragraph breaks where naive stripping yields none,
    which is the difference between a chunker having boundaries and not.
    """
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    from markitdown import MarkItDown
    return MarkItDown().convert(str(path)).text_content


def chunk(text: str, size: int) -> list[str]:
    """Split with langchain's recursive splitter, measured in words.

    It walks a separator ladder (paragraph, line, sentence, word) and falls
    through when a piece is still too big, so a book that arrives as one
    unbroken blob still splits. A hand-rolled paragraph splitter silently
    returns the whole book as a single chunk in that case.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=int(size * 0.02),   # a little carry-over so ideas are not cut mid-argument
        length_function=lambda t: len(t.split()),
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def run_claude(prompt: str, timeout: int, tools: str, body: str | None = None) -> tuple[bool, str]:
    """Run one claude -p pass. Bulk text goes on stdin, never argv.

    A 25k-word chunk is ~150KB, well past ARG_MAX, so passing it as an argument
    fails with 'Argument list too long' before claude even starts.
    """
    try:
        res = subprocess.run(
            [CLAUDE, "-p", prompt, "--allowedTools", *tools.split(),
             "--permission-mode", "acceptEdits"],
            input=body, capture_output=True, text=True, timeout=timeout, cwd=str(VAULT),
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    return res.returncode == 0, (res.stdout or res.stderr or "").strip()


# ── map: read a chunk, keep only what survives summarizing ─────────────────
MAP_PROMPT = """You are reading part {i} of {n} of "{title}".

Pull out only what would still matter to someone a year from now. Be ruthless: a
chunk of a book usually contains two or three ideas worth keeping and a lot of
elaboration around them.

Return plain markdown, no preamble:

## Claims
- each substantive claim the author actually argues, one line, in your own words

## Frameworks
- any named model, ratio, rule, or procedure, with enough detail to apply it

## Examples
- concrete cases, companies, or numbers used as evidence, one line each

## Quotable
- at most 2 short passages (under 25 words) that state something better than a paraphrase would

Omit a section entirely if this chunk has nothing for it. Do not summarize the
narrative. Do not pad.

The text of this part arrives on stdin."""


REDUCE_PROMPT = """You have finished reading "{title}" ({words:,} words) in {n} passes.
Below are your own notes from each pass.

Write it into the vault now, following wiki/SCHEMA.md. Read SCHEMA.md and
index.md first, and check for existing related pages before creating anything.

Create exactly:

1. ONE source page at wiki/sources/{title}.md
   The book's actual argument in your words: what it claims, what it is for,
   who should read it, and where it is weak or dated. Not a chapter summary.

2. UP TO FIVE concept pages in wiki/concepts/ for ideas from this book that are
   genuinely new to the vault. Check first. If the vault already covers an idea,
   UPDATE that page with what this book adds and link it, do not duplicate it.
   Fewer good pages beat five mediocre ones. Zero is a valid answer.

3. ONE candidate decision at wiki/decisions/{title} - Decision.md
   Phrased as a QUESTION this book forces for Nitesh specifically, with the
   defensible positions on each side. He does data engineering at Living Spaces,
   runs NiteshTechAI on X, and trades via a paper-trading bot on the Big 3
   strategy. Do not answer the question. He answers it.

Every page needs required frontmatter and at least 2 [[Exact Page Title]] links.
Update index.md and append one entry to log.md.

Report every file you created or updated.

Your notes from all {n} passes arrive on stdin."""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest a book as one synthesis, not many fragments.")
    ap.add_argument("book")
    ap.add_argument("--chunk-words", type=int, default=CHUNK_WORDS)
    ap.add_argument("--dry-run", action="store_true", help="extract and chunk, write nothing")
    args = ap.parse_args()

    path = Path(args.book).expanduser()
    if not path.exists():
        sys.exit(f"not found: {path}")

    title = re.sub(r"\s*\(\d{4}\)\s*$", "", path.stem).strip()
    log(f"extracting {path.name}")
    text = extract(path)
    words = len(text.split())
    if words < 2000:
        sys.exit(f"only {words} words extracted, this looks scanned or empty (try ocrmypdf first)")

    chunks = chunk(text, args.chunk_words)
    log(f"{title}: {words:,} words -> {len(chunks)} passes of ~{args.chunk_words:,}")

    if args.dry_run:
        log("dry run, stopping here")
        print(f"\nfirst 400 chars:\n  {text[:400]}")
        return 0

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes_file = NOTES_DIR / f"{re.sub(r'[^\w -]', '', title)[:60]}.md"
    collected: list[str] = []

    for i, body in enumerate(chunks, 1):
        log(f"pass {i}/{len(chunks)} ({len(body.split()):,} words)")
        ok, out = run_claude(
            MAP_PROMPT.format(i=i, n=len(chunks), title=title),
            MAP_TIMEOUT, "Read", body=body,
        )
        if not ok:
            log(f"  pass {i} failed: {out[:200]}")
            continue
        collected.append(f"### Pass {i}\n{out}")
        notes_file.write_text("\n\n".join(collected), encoding="utf-8")

    if not collected:
        sys.exit("every pass failed, nothing to synthesize")
    log(f"notes: {notes_file} ({sum(len(c.split()) for c in collected):,} words from {words:,})")

    log("synthesizing into the vault")
    ok, out = run_claude(
        REDUCE_PROMPT.format(title=title, words=words, n=len(collected)),
        REDUCE_TIMEOUT, "Read Write Edit Glob Grep", body="\n\n".join(collected),
    )
    print(out[-3000:] if out else "(no output)")
    if not ok:
        log("ALERT synthesis pass failed, notes are kept for a retry")
        return 1
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
