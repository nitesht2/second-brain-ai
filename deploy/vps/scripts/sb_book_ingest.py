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
import fcntl
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


READABLE = (".epub", ".pdf", ".txt", ".md", ".docx", ".html")


def title_of(path: Path) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", path.stem).strip()


def already_done(title: str) -> bool:
    """A source page for this title means the book has been through the reducer."""
    return (VAULT / "wiki" / "sources" / f"{title}.md").exists()


def ingest_one(path: Path, chunk_words: int, dry_run: bool) -> bool:
    title = title_of(path)
    log(f"extracting {path.name}")
    try:
        text = extract(path)
    except Exception as exc:  # noqa: BLE001 - one bad book must not stop a folder run
        log(f"  SKIP unreadable ({type(exc).__name__}: {exc})")
        return False
    words = len(text.split())
    if words < 2000:
        log(f"  SKIP only {words} words, looks scanned or empty (try ocrmypdf)")
        return False

    chunks = chunk(text, chunk_words)
    log(f"{title}: {words:,} words -> {len(chunks)} passes of ~{chunk_words:,}")
    if dry_run:
        log("  dry run, nothing written")
        return True

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
        log("  every pass failed, nothing to synthesize")
        return False
    log(f"notes: {notes_file.name} ({sum(len(c.split()) for c in collected):,} words from {words:,})")

    # The reduce pass writes wiki pages, index.md and log.md, the same files the
    # watcher's sb_ingest.sh and vault_backup.sh touch. Every other writer takes
    # this lock; without it a book landing mid-ingest corrupts the shared index.
    log("synthesizing into the vault (waiting for the ingest lock)")
    with open(VAULT / ".ingest.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ok, out = run_claude(
            REDUCE_PROMPT.format(title=title, words=words, n=len(collected)),
            REDUCE_TIMEOUT, "Read Write Edit Glob Grep", body="\n\n".join(collected),
        )
    if not ok:
        log("  ALERT synthesis failed, notes kept for a retry")
        return False
    print(out[-2000:] if out else "(no output)")
    log(f"done: {title}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest a book as one synthesis, not many fragments.")
    ap.add_argument("book", nargs="?", help="a single book file")
    ap.add_argument("--folder", help="walk a directory and ingest each book in turn")
    ap.add_argument("--limit", type=int, default=0, help="stop after N books (0 = no cap)")
    ap.add_argument("--pause", type=int, default=60, help="seconds between books (default 60)")
    ap.add_argument("--chunk-words", type=int, default=CHUNK_WORDS)
    ap.add_argument("--dry-run", action="store_true", help="extract and chunk, write nothing")
    ap.add_argument("--redo", action="store_true", help="reingest even if a source page exists")
    args = ap.parse_args()

    if not args.book and not args.folder:
        ap.error("give a book path or --folder")

    # ── single book ────────────────────────────────────────────────────────
    if args.book:
        path = Path(args.book).expanduser()
        if not path.exists():
            sys.exit(f"not found: {path}")
        return 0 if ingest_one(path, args.chunk_words, args.dry_run) else 1

    # ── folder ─────────────────────────────────────────────────────────────
    root = Path(args.folder).expanduser()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    books = sorted(p for p in root.rglob("*") if p.suffix.lower() in READABLE and p.is_file())
    skipped = [p for p in books if not args.redo and already_done(title_of(p))]
    todo = [p for p in books if p not in skipped]
    if args.limit:
        todo = todo[: args.limit]

    unreadable = sorted({p.suffix.lower() for p in root.rglob("*")
                         if p.is_file() and p.suffix.lower() not in READABLE and p.suffix})
    log(f"{len(books)} readable book(s) under {root}")
    log(f"  {len(skipped)} already in the vault, {len(todo)} to do this run")
    if unreadable:
        log(f"  ignoring other formats present: {' '.join(unreadable)}")
    if not todo:
        log("nothing to do")
        return 0

    ok_count = 0
    for n, path in enumerate(todo, 1):
        log(f"── book {n}/{len(todo)}: {path.name}")
        if ingest_one(path, args.chunk_words, args.dry_run):
            ok_count += 1
        if n < len(todo) and args.pause and not args.dry_run:
            log(f"  pausing {args.pause}s")
            time.sleep(args.pause)

    log(f"folder run finished: {ok_count}/{len(todo)} ingested")
    return 0 if ok_count else 1


if __name__ == "__main__":
    sys.exit(main())
