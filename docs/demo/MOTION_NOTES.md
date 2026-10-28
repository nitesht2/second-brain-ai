# Visual and motion notes

How the README visuals were made, and the references behind them, so they stay
consistent as the project grows.

## Files

| Output | Source | Rebuild |
|---|---|---|
| `docs/screenshots/banner.png` | `docs/demo/banner.html` | `node docs/demo/render.js` |
| `docs/screenshots/before-after-{light,dark}.png` | `docs/demo/before-after.html` | `node docs/demo/render.js` |
| `docs/screenshots/architecture-{light,dark}.svg` | `docs/diagrams/src/architecture.d2` | `python3 docs/diagrams/src/build.py` (needs [D2](https://d2lang.com)) |
| `docs/screenshots/hero.{mp4,gif}` | `docs/demo/film/hero.html` + `film/graph.json` | `python3 docs/demo/film/graph.py` then `node docs/demo/film/render.js` |

All HTML sources load the bundled fonts in `docs/demo/fonts/` (Inter and
Instrument Serif, SIL Open Font License).

## Look

- Ground: deep navy `#060a16`, a fine grid that fades out from the centre, one
  soft blue light. Inspired by [inboxapp.com](https://inboxapp.com/home).
- Type: Inter for everything; one accent word in Instrument Serif italic
  ("*connected.*").
- Colour has one meaning everywhere: blue = sources, orange = people and
  tools, green = concepts, purple = synthesis. In the architecture diagram:
  blue = local mode, purple = always-on mode, green = shared.
- Content is real: every note title, link and article excerpt comes from
  `examples/demo-vault`. Nothing invented is shown as real.

## Motion rules used for the hero film

Taken from open-source agent skills listed on
[motionvideo.xyz/skills](https://motionvideo.xyz/en/skills) and
[skill-issue.in](https://skill-issue.in/?domain=motion-graphics):

- [motionmaxxing](https://github.com/Tejashmakwana/motionmaxxing): every beat
  earns one belief (save → notes → graph → payoff); shots hand off (the article
  becomes the source note, phrases grow into notes, notes collapse into graph
  nodes); no page chrome, counters or scene labels; arrivals decelerate from
  oversize, exits accelerate; end hold ≤ 1.4 s.
- [LottieFiles motion-design-skill](https://github.com/LottieFiles/motion-design-skill):
  "premium" personality (no overshoot), entrances longer than exits, staggered
  words a few frames apart.
- [claude-motion-design](https://github.com/howseen-ai/claude-motion-design):
  deterministic `window.seek(t)` page rendered frame by frame with Playwright,
  then ffmpeg. No CSS transitions or timers, so every render is identical.
- Also worth a look for future videos: [Remotion skills](https://www.remotion.dev/docs/ai/skills),
  [HyperFrames](https://github.com/heygen-com/hyperframes-community-skills),
  [GSAP skills](https://github.com/greensock/gsap-skills),
  [Product Launch Motion](https://github.com/AbubakrChan/product-launch-motion).
