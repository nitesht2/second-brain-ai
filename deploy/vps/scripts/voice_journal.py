#!/usr/bin/env python3
"""Voice journal: an audio memo -> a transcribed entry in your private journal.

This is the journaling/affirmation/manifestation lane. Unlike clip.py (which
feeds the knowledge wiki), voice memos here are PRIVATE: they land in
journal/<YYYY-MM-DD>.md and are NOT ingested, cross-linked, or sent to the
wiki agent. Record on your phone, get the audio onto the box, wake up to a
dated journal entry.

Transcription is faster-whisper on CPU (int8), the same engine clip.py uses.
Default model is multilingual `base` (not base.en) so affirmations in any
language transcribe — override with VOICE_JOURNAL_MODEL or --model.

Usage:
    voice_journal.py memo.m4a [memo2.ogg ...]   # transcribe one or more files
    voice_journal.py --inbox                     # transcribe everything in journal/inbox/
    voice_journal.py memo.m4a --model small      # bigger model (slower, better)

Each transcribed file is appended (timestamped) to today's journal entry, then
moved to journal/processed/ as an audit trail.
"""
import os
import re
import sys
from pathlib import Path
from datetime import datetime

VAULT = Path(os.environ.get("SECOND_BRAIN_VAULT", str(Path.home() / "SecondBrain")))
JOURNAL = VAULT / "journal"
INBOX = JOURNAL / "inbox"
PROCESSED = JOURNAL / "processed"
# Multilingual by default so non-English affirmations/manifestations work.
# Set VOICE_JOURNAL_MODEL=base.en if your journal is English-only (faster).
MODEL = os.environ.get("VOICE_JOURNAL_MODEL", "base")

# Audio containers faster-whisper/ffmpeg can read. Voice-memo apps emit m4a/aac;
# Discord voice messages are ogg/opus; recorders vary.
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".webm", ".3gp"}


def transcribe(audio: Path) -> str:
    """Return the spoken text of an audio file (faster-whisper, CPU int8)."""
    from faster_whisper import WhisperModel
    wm = WhisperModel(MODEL, device="cpu", compute_type="int8")
    # base.en is English-only; any other model is multilingual (auto-detect).
    lang = "en" if MODEL.endswith(".en") else None
    segs, _ = wm.transcribe(str(audio), language=lang)
    return " ".join(s.text.strip() for s in segs).strip()


def journal_path(day: datetime) -> Path:
    """Today's journal file, creating the journal dir + a fresh header if new."""
    JOURNAL.mkdir(parents=True, exist_ok=True)
    fp = JOURNAL / f"{day:%Y-%m-%d}.md"
    if not fp.exists():
        fp.write_text(
            f"---\n"
            f"type: journal\n"
            f"date: {day:%Y-%m-%d}\n"
            f"tags: [journal, voice]\n"
            f"private: true\n"
            f"---\n\n"
            f"# Journal — {day:%A, %B %-d, %Y}\n\n",
            encoding="utf-8",
        )
    return fp


def append_entry(text: str, audio: Path, when: datetime) -> Path:
    """Append a timestamped transcript block to today's journal file."""
    fp = journal_path(when)
    block = (
        f"## {when:%H:%M}\n\n"
        f"{text}\n\n"
        f"<sub>🎙️ voice memo · `{audio.name}` · whisper {MODEL}</sub>\n\n"
    )
    with fp.open("a", encoding="utf-8") as f:
        f.write(block)
    return fp


def archive(audio: Path) -> None:
    """Move a processed memo into journal/processed/ (audit trail, dedup-safe)."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED / audio.name
    if dest.exists():  # avoid clobbering a same-named earlier memo
        dest = PROCESSED / f"{audio.stem}-{datetime.now():%H%M%S}{audio.suffix}"
    audio.replace(dest)


def process(audio: Path) -> int:
    """Transcribe one memo into the journal. Returns 0 on success, 1 on failure."""
    if not audio.is_file():
        print(f"skip (not a file): {audio}")
        return 1
    if audio.suffix.lower() not in AUDIO_EXTS:
        print(f"skip (not audio): {audio.name}")
        return 1
    print(f'transcribing "{audio.name}" (whisper {MODEL})...')
    try:
        text = transcribe(audio)
    except Exception as e:
        print(f"transcribe failed for {audio.name}: {e} (left in place to retry)")
        return 1
    if not text:
        print(f"no speech detected in {audio.name} (left in place)")
        return 1
    when = datetime.now()
    fp = append_entry(text, audio, when)
    archive(audio)
    print(f"journaled {audio.name} -> {fp.name} ({len(text)}c) · audio -> journal/processed/")
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--model" in sys.argv:
        global MODEL
        MODEL = sys.argv[sys.argv.index("--model") + 1]

    if "--inbox" in sys.argv or not args:
        INBOX.mkdir(parents=True, exist_ok=True)
        targets = sorted(p for p in INBOX.iterdir()
                         if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
        if not targets:
            print(f"nothing to do: no audio in {INBOX}")
            return 0
    else:
        targets = [Path(a).expanduser() for a in args]

    rc = 0
    for audio in targets:
        rc |= process(audio)
    return rc


if __name__ == "__main__":
    sys.exit(main())
