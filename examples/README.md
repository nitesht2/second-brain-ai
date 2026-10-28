# Demo vault

`demo-vault/` is a small, finished Second Brain on a neutral topic (learning, memory, and note-taking). Use it to see what the system produces before you set anything up, or to record demos and screenshots.

All source texts in `raw/` are short samples written for this demo. The wiki notes follow the exact format `auto_ingest.py` writes.

| Folder | Contents |
|---|---|
| `raw/processed/` | 4 inputs that were already ingested |
| `raw/` | 2 inputs waiting to be ingested, so you can watch a real run |
| `wiki/sources/` | One note per ingested input |
| `wiki/entities/` | People and tools (Ebbinghaus, Luhmann, Anki, Obsidian, ...) |
| `wiki/concepts/` | Ideas (Spaced Repetition, Zettelkasten, Deep Work, ...) |
| `wiki/synthesis/` | Cross-note insights generated from clusters |
| `.obsidian/graph.json` | Graph view colored by note type, index hidden |

## Look at it (no API key needed)

In Obsidian: **Open folder as vault** → select `examples/demo-vault` → open **Graph view**.

Colors: blue = sources, orange = entities, green = concepts, purple = synthesis. The vault starts as two separate clusters: memory and learning, and note-taking.

## Run a real ingest on it

Work on a copy so the repo stays clean:

```bash
scripts/demo_reset.sh
SECOND_BRAIN_PATH=~/SecondBrainDemo python3 auto_ingest.py
```

The two waiting files (`why-we-forget.md`, `evergreen-notes.md`) become new wiki notes. `evergreen-notes.md` ties note-taking to active recall and the Feynman Technique, so the model usually links the two clusters together. Run `scripts/demo_reset.sh` again to start over.
