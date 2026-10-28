# Screenshots

Drop your screenshots here for the main README:

- `graph-view.png` — Obsidian graph view with connected nodes
- `obsidian-vault.png` — Obsidian sidebar showing vault structure
- `ingest-terminal.png` — Terminal output of auto_ingest.py running
- `query-result.png` — Claude Code running /second-brain-query
- `lint-report.png` — /second-brain-lint report output
- `before-after-light.png` / `before-after-dark.png` — Generated from
  [`docs/demo/before-after.html`](../demo/before-after.html); re-render with `node docs/demo/render.js`
- `architecture-light.svg` / `architecture-dark.svg` — README architecture diagram, from
  [`docs/diagrams/src/architecture.d2`](../diagrams/src/architecture.d2); rebuild with `python3 docs/diagrams/src/build.py` (needs [D2](https://d2lang.com))
- `banner.png` — README header and GitHub social preview (1280×640), from
  [`docs/demo/banner.html`](../demo/banner.html)
- `hero.gif` / `hero.mp4` — 12.5s animation at the top of the README, built in code from
  [`docs/demo/film/hero.html`](../demo/film/hero.html); re-render with `node docs/demo/film/render.js`
- `demo.gif` — 15–20s GIF of the full flow (clip → ingest → graph update).
  Step-by-step recording guide: [`docs/demo/RECORDING.md`](../demo/RECORDING.md)

The README references these files with:
```markdown
![Graph View](docs/screenshots/graph-view.png)
```
