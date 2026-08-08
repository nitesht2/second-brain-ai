# Journal

Your **private** voice journal — for journaling, affirmations, and
manifestation. This is deliberately separate from the knowledge wiki: entries
here are **not ingested, not cross-linked, and never sent to the wiki agent**.

## How it works

```
record a voice memo  →  drop the audio in journal/inbox/
   →  sb_journal_watcher.sh (inotify)  →  voice_journal.py (faster-whisper)
   →  a timestamped entry in journal/<YYYY-MM-DD>.md  →  audio moved to journal/processed/
```

- **`inbox/`** — drop zone. Any `.m4a/.mp3/.wav/.ogg/.opus/...` that lands here
  gets transcribed automatically. Get audio here however suits you: a phone
  voice-memo synced via Syncthing, a Discord voice message you download, AirDrop
  to a synced folder, `scp`, etc.
- **`processed/`** — audit trail of memos already transcribed.
- **`<date>.md`** — one file per day; every memo that day is appended as a
  timestamped `## HH:MM` block.

## Manual use (no watcher needed)

```bash
# transcribe a single memo
.venv/bin/python scripts/voice_journal.py ~/memo.m4a

# drain everything sitting in journal/inbox/
.venv/bin/python scripts/voice_journal.py --inbox

# bigger model for a tricky recording (slower, more accurate)
.venv/bin/python scripts/voice_journal.py ~/memo.m4a --model small
```

The transcription model defaults to multilingual `base` so affirmations in any
language work. Set `VOICE_JOURNAL_MODEL=base.en` for an English-only journal
(a bit faster), or `small`/`medium` for higher accuracy.
