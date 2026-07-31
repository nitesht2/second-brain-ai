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
import hashlib
import os
import re
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

VAULT = Path(os.environ.get("SB_VAULT", "/root/SecondBrain"))
CLAUDE = os.environ.get("SB_CLAUDE", "/usr/local/bin/claude")
NOTES_DIR = VAULT / "outputs" / "book-notes"
CHUNK_WORDS = 45_000        # ~60k tokens, still well inside one pass
# 25k was already 7x the old doc2md sizing and left most of the window unused. At 45k
# a 270k-word book is 7 passes instead of 16, which roughly halves the map phase. The
# reduce phase is unchanged and dominates total runtime either way.
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

Pull out only what would still matter to someone a year from now. Be ruthless: most
of a book is elaboration around a much smaller number of real ideas, and this is a
long stretch of one, so expect to discard the majority of what you read. Do not pad
toward a quota, and do not compress so hard that a distinct idea is lost because a
neighbouring one was stronger.

Return plain markdown, no preamble:

## Claims
- each substantive claim the author actually argues, one line, in your own words

## Frameworks
- any named model, ratio, rule, or procedure, with enough detail to apply it

## Examples
- concrete cases, companies, or numbers used as evidence, one line each

## Quotable
- at most 2 short passages (under 25 words) that state something better than a paraphrase would

## Doubts
- claims this chunk asserts without evidence, numbers with no derivation, places the
  author contradicts himself or an earlier chunk, and anything that reads as selling
  something. One line each.

Omit a section entirely if this chunk has nothing for it. Do not summarize the
narrative. Do not pad.

The text of this part arrives on stdin."""


REDUCE_PROMPT = """You have finished reading "{title}" ({words:,} words) in {n} of {n_total} passes.

Write it into the vault now, following wiki/SCHEMA.md.

Read wiki/SCHEMA.md in full. Do NOT read wiki/index.md, it is ~70k tokens and the
vault's own rules forbid loading it. Grep it instead. Before you create ANY page, for
each idea you are considering run at least three greps: index.md with three different
names for the idea, and `grep -ril` over wiki/ for its two most distinctive phrases.
Report those greps and their hit counts at the end. A check you did not run is not a check.

These decisions are already open in the vault. Read any that could plausibly overlap
this book BEFORE you write anything:

{decisions}

Create:

1. ONE source page at wiki/sources/{title}.md
   The book's actual argument in your words: what it claims, what it is for, and who
   should read it. Not a chapter summary. It must end with these two sections:

   ## Where it is weak or dated
   What does this book assert without evidence? What would a skeptic of THIS AUTHOR,
   not of the field, push back on? What has time falsified? Does the author sell the
   tool, service or fund his method requires? Anywhere your notes show him breaking or
   exempting himself from his own rule goes here. Every bullet either quotes the notes
   or is marked "(outside the book)". Grep wiki/sources for weaknesses already stated
   about other books from this shelf: do not repeat a shelf-wide limitation as if it
   were this book's flaw. At least one bullet must be something THIS book gets wrong
   that its neighbours do not. A book not covering what it never claimed to cover is a
   fit question, not a weakness.

   ## Verdict
   One line: is this worth Nitesh's time relative to books already in wiki/sources on
   this topic, and if a vault page covers the same ground better, name it.

2. UP TO FIVE concept pages in wiki/concepts/ for ideas genuinely new to the vault.
   Check with greps, not recall. If the vault already covers an idea, UPDATE that page
   with what this book adds and link it. A new page must state a claim that would
   change a decision differently from every existing page; if the difference is a use
   case or a facet of the same claim, it is a section on an existing page. Two is a
   normal outcome. Five means you probably duplicated something. Zero is valid.

3. UPDATES to existing pages. List every existing concept page this book bears on. For
   each, either update it with a paragraph attributed to this book plus a link, or say
   in one line why this book adds nothing. This is a deliverable, not a side effect.

4. AT MOST ONE candidate decision, and zero is valid and expected for the Nth book on
   one shelf. If any open decision above already poses this question, do NOT create a
   file: add this book's angle to that page as a new position with its own For/Against,
   or as a sharper discriminating sub-question, and say so in your report. Only create
   wiki/decisions/{title} - Decision.md when the question genuinely cannot live inside
   an existing decision, and state in one line why. If your For/Against bullets could
   be pasted into an existing decision unchanged, you are writing a duplicate: cut them
   and write only what this book supports. Phrase it as a QUESTION this book forces for
   Nitesh specifically, with defensible positions on each side. He does data engineering
   at Living Spaces, runs NiteshTechAI on X, and trades a paper-trading options bot on
   the Big 3 strategy. Do not answer it. He answers it.

Frontmatter is not optional and is not to be inferred from neighbouring pages.

Source page:
---
title: "<exact page title, identical to the filename without .md>"
type: source
source_type: book
source_url: ""
valid_from: <today YYYY-MM-DD>
learned_on: <today YYYY-MM-DD>
confidence: high|medium|low
generated_by: <your model id>
human_reviewed: false
tags: [...]
---
confidence describes how far the BOOK can be trusted, not how sure you are of your
summary. high = still correct today, medium = superseded in parts, low = period interest.

Concept page:
---
type: concept
valid_from: <today YYYY-MM-DD>
last_verified: <today YYYY-MM-DD>
confidence: high|medium|low
explored: false
generated_by: <your model id>
human_reviewed: false
---

Decision page:
---
title: "<the question>"
type: decision
status: open
valid_from: <today YYYY-MM-DD>
last_verified: <today YYYY-MM-DD>
generated_by: <your model id>
human_reviewed: false
tags: [...]
---
Do not emit decided_on at all while the question is unanswered.

Every page needs at least 2 [[Exact Page Title]] links. NEVER break a [[wikilink]]
across a line: keep each [[...]] entirely on one line however long it runs. The text
inside [[ ]] must be the exact filename without .md.

Append one entry to log.md, and update index.md including its Last updated line, its
Total entries count, and the count in every section heading you changed.

End with a report in exactly this shape, asserting nothing you did not do:
  Created: <path>
  Updated: <path> - what you added   (or "none, because ...")
  Decision: created <path> because ... | appended to <path> | none, because ...
  Greps run: <query> -> <hit count>

Your notes from all {n} passes arrive on stdin."""


READABLE = (".epub", ".pdf", ".txt", ".md", ".docx", ".html")

# Books whose title collides with another edition on the same shelf, resolved to a
# year-suffixed title by the folder pass so neither edition is dropped.
TITLE_OVERRIDE: dict[Path, str] = {}


def _epub_title(path: Path) -> str | None:
    """dc:title (+ dc:creator) from the OPF. None for non-epub or on any failure."""
    if path.suffix.lower() != ".epub":
        return None
    try:
        with zipfile.ZipFile(path) as z:
            opf = next(n for n in z.namelist() if n.lower().endswith(".opf"))
            root = ET.fromstring(z.read(opf))
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        t = (root.findtext(".//dc:title", namespaces=ns) or "").strip()
        a = (root.findtext(".//dc:creator", namespaces=ns) or "").strip()
    except Exception:
        return None
    # Metadata is not automatically better than the filename: some epubs carry an
    # ASIN or ISBN as dc:title (B000YIWF4C EBOK), in which case the stem is the
    # real title. Reject those and let the caller fall through.
    if not t or re.fullmatch(r"[0-9A-Z]{6,}(\s+EBOK)?", t.strip()):
        return None
    if ":" in t and len(t) > 60:
        t = t.split(":", 1)[0]
    t = re.sub(r'[\\/:*?"<>|]', " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return f"{t} - {a}" if a else t


def title_of(path: Path, disambiguate: bool = False) -> str:
    """The file stem is not a title. Calibre exports arrive truncated at 30 chars,
    colon-mangled into underscores, or as a bare ISBN. Prefer embedded metadata,
    then the containing folder, then the stem."""
    meta = _epub_title(path)
    if meta:
        if disambiguate:
            year = re.search(r"\((\d{4})\)", path.stem)
            if year:
                return f"{meta} ({year.group(1)})"
        return meta
    stem = re.sub(r"\s*\(\d{4}\)\s*$", "", path.stem).strip()
    # Only an ISBN-shaped stem justifies falling back to the folder. A length test
    # cannot tell a truncated title from a real one: "Financial Analysis Using
    # Excel" is exactly 30 characters and is not truncated.
    if re.fullmatch(r"[0-9A-Z]{6,}", stem):
        stem = re.sub(r"\s*\(\d{4}\)\s*$", "", path.parent.name).strip()
    out = re.sub(r"\s+", " ", stem.replace("_s ", "'s ").replace("_ ", ": ")
                 .replace(":", " -")).strip()
    if disambiguate:
        year = re.search(r"\((\d{4})\)", path.stem)
        if year:
            out = f"{out} ({year.group(1)})"
    return out


def skip_marker(path: Path) -> Path:
    """Set when a book cannot be read at all. Extraction is deterministic, so
    retrying costs a --limit slot every run and never succeeds; without this one
    unparseable PDF sits at the head of the queue forever."""
    return NOTES_DIR / f"{_file_key(path)}.skip"


def _file_key(path: Path) -> str:
    return hashlib.md5(f"{path.name}:{path.stat().st_size}".encode()).hexdigest()[:16]


def done_marker(path: Path) -> Path:
    """Keyed on the file, not the title. Titles are derived and the derivation
    changes; a marker that moves when the naming rule improves silently re-ingests
    everything already done."""
    return NOTES_DIR / f"{_file_key(path)}.done"


def already_done(path: Path) -> bool:
    """Set only after the reduce pass returned success.

    Keying on the source page was wrong: it lands ~178s into a ~451s reduce, so a
    reduce dying in the last 61% left a half-written book that a re-run then skipped.
    """
    return done_marker(path).exists() or skip_marker(path).exists()


def open_decisions() -> str:
    """Titles of decisions already open, so a book can merge instead of duplicating."""
    lines = []
    for p in sorted((VAULT / "wiki" / "decisions").glob("*.md")):
        head = p.read_text(encoding="utf-8", errors="ignore")[:400]
        m = re.search(r'^title:\s*"?(.+?)"?\s*$', head, re.MULTILINE)
        lines.append(f"- [[{p.stem}]] : {m.group(1) if m else p.stem}")
    return "\n".join(lines) or "(none yet)"


def ingest_one(path: Path, chunk_words: int, dry_run: bool) -> bool:
    title = TITLE_OVERRIDE.get(path) or title_of(path)
    log(f"extracting {path.name}")
    try:
        text = extract(path)
    except Exception as exc:  # noqa: BLE001 - one bad book must not stop a folder run
        log(f"  SKIP unreadable ({type(exc).__name__}: {exc})")
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        skip_marker(path).write_text(f"{path.name}: {type(exc).__name__}\n", encoding="utf-8")
        return False
    words = len(text.split())
    if words < 2000:
        log(f"  SKIP only {words} words, looks scanned or empty (try ocrmypdf)")
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        skip_marker(path).write_text(f"{path.name}: only {words} words\n", encoding="utf-8")
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
            REDUCE_PROMPT.format(title=title, words=words, n=len(collected),
                             n_total=len(chunks), decisions=open_decisions()),
            REDUCE_TIMEOUT, "Read Write Edit Glob Grep", body="\n\n".join(collected),
        )
    if not ok:
        log("  ALERT synthesis failed, notes kept for a retry")
        return False

    # A [[link]] wrapped across a newline resolves to nothing in Obsidian. Normalize
    # whitespace inside every wikilink target, which also clears ones predating this.
    fixed_pages = 0
    for page in (VAULT / "wiki").rglob("*.md"):
        text = page.read_text(encoding="utf-8", errors="ignore")
        fixed = re.sub(r"\[\[([^\]]*?)\]\]",
                       lambda m: "[[" + re.sub(r"\s+", " ", m.group(1)).strip() + "]]", text)
        if fixed != text:
            page.write_text(fixed, encoding="utf-8")
            fixed_pages += 1
    if fixed_pages:
        log(f"  repaired wrapped wikilinks in {fixed_pages} page(s)")

    print(out[-2000:] if out else "(no output)")
    done_marker(path).write_text(f"{title}\n", encoding="utf-8")
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

    # A shelf holds the same work twice: epub + pdf of one title, or literal copies.
    # Ingesting both mints two source pages for one book and splits its inbound links.
    seen: dict[str, Path] = {}
    for p in list(books):
        h = hashlib.md5(p.read_bytes()).hexdigest()
        if h in seen:
            log(f"  duplicate bytes, skipping {p.name} (same as {seen[h].name})")
            books.remove(p)
            continue
        seen[h] = p
    # Same title with different bytes is usually a different edition, not a
    # duplicate. Dropping one loses a book; disambiguate with the year instead.
    by_title: dict[str, list[Path]] = {}
    for p in books:
        by_title.setdefault(title_of(p), []).append(p)
    ambiguous = {t for t, g in by_title.items() if len(g) > 1}
    for t in sorted(ambiguous):
        log(f"  {len(by_title[t])} editions share the title {t!r}, keeping all, year appended")
    TITLE_OVERRIDE.update({p: title_of(p, disambiguate=True)
                           for t in ambiguous for p in by_title[t]})

    skipped = [p for p in books if not args.redo and already_done(p)]
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
