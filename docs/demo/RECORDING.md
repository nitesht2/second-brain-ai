# Recording a real screen demo

The animated hero at the top of the README (`docs/screenshots/hero.gif`) is built in code, see [MOTION_NOTES.md](MOTION_NOTES.md). This guide is for a real screen recording of Obsidian, which makes good proof next to it (a launch post, the README's "What the agent writes" section).

Goal: a 15–20 second loop that shows the whole idea: **save a link → run ingest → the graph grows.**

## Setup (once)

- [ ] `scripts/demo_reset.sh` to create a clean `~/SecondBrainDemo`
- [ ] API key in `~/.secondbrain.env` (see the README)
- [ ] Open `~/SecondBrainDemo` as a vault in Obsidian
- [ ] Obsidian: dark theme, hide the left sidebar, open Graph view in the main pane
- [ ] Terminal: large font (18pt+), dark theme, about 100×20 characters, `cd` to the repo
- [ ] Arrange: Obsidian graph on the left two thirds, terminal on the right third
- [ ] Do one full practice run, then run `scripts/demo_reset.sh` again and reopen the vault
- [ ] Recorder: [Kap](https://getkap.co) or the macOS screenshot tool (⌘⇧5), 1920×1080 or smaller

## Shot list

| Time | On screen | Caption (add in editing) |
|---|---|---|
| 0–3s | The graph as it starts: two separate clusters | **Your notes, before** |
| 3–6s | Finder: drag `evergreen-notes.md` and `why-we-forget.md` into `raw/` (or show them already there) | **Drop in anything you read** |
| 6–12s | Terminal: `SECOND_BRAIN_PATH=~/SecondBrainDemo python3 auto_ingest.py`; the `+ [created]` lines scroll by | **AI writes linked wiki notes** |
| 12–18s | Back to the graph: new nodes appear and the two clusters join | **It connects ideas for you** |
| 18–20s | Hold on the final graph | **Second Brain AI** |

The ingest takes longer than 6 seconds in real time. Speed it up in editing, or cut from the command to the finished output.

## Export

- Target under 5 MB so GitHub shows it inline: 960px wide, 12–15 fps
- Convert a screen recording with [gifski](https://gif.ski): `gifski --fps 12 --width 960 -o docs/screenshots/demo.gif recording.mov`
- Save as `docs/screenshots/demo.gif`.
- Also keep the `.mp4`. X and LinkedIn play video better than GIFs.

## Still screenshots to grab while you're set up

- `docs/screenshots/demo-graph-before.png`: the starting graph
- `docs/screenshots/demo-graph-after.png`: the graph after ingest
- `docs/screenshots/ingest-terminal.png`: the terminal output
