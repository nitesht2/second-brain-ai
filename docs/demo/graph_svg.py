"""Draw the demo vault's link graph as an SVG for the README banner.

Usage: python3 docs/demo/graph_svg.py > docs/demo/banner-graph.svg

Includes the two notes the pending raw/ files produce, so the banner shows the
vault after an ingest (one connected graph instead of two clusters).
"""
import math
import random
import re
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2] / "examples" / "demo-vault" / "wiki"
COLORS = {"sources": "#4f8ef7", "entities": "#f5a623", "concepts": "#4ade80", "synthesis": "#c084fc"}
AFTER_INGEST = {
    "Evergreen Notes": ("concepts", ["Zettelkasten", "Atomic Notes", "Feynman Technique", "Active Recall"]),
    "Forgetting Curve": ("concepts", ["Hermann Ebbinghaus", "Spaced Repetition", "Active Recall"]),
}
W, H, MARGIN = 540, 540, 30

nodes = {p.stem: p.parent.name for p in WIKI.rglob("*.md") if p.parent.name in COLORS}
edges = set()
for p in WIKI.rglob("*.md"):
    if p.stem in nodes:
        for link in re.findall(r"\[\[([^\]]+)\]\]", p.read_text(encoding="utf-8")):
            if link in nodes and link != p.stem:
                edges.add(tuple(sorted((p.stem, link))))
for name, (kind, links) in AFTER_INGEST.items():
    nodes[name] = kind
    edges.update(tuple(sorted((name, l))) for l in links)

random.seed(11)
pos = {n: [random.uniform(-1, 1), random.uniform(-1, 1)] for n in nodes}
names = list(nodes)
for _ in range(800):
    force = {n: [0.0, 0.0] for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            k = 0.02 / (dx * dx + dy * dy + 1e-4)
            force[a][0] += dx * k; force[a][1] += dy * k
            force[b][0] -= dx * k; force[b][1] -= dy * k
    for a, b in edges:
        dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
        d = math.hypot(dx, dy) + 1e-6
        k = (d - 0.28) * 0.05
        force[a][0] += dx / d * k; force[a][1] += dy / d * k
        force[b][0] -= dx / d * k; force[b][1] -= dy / d * k
    for n in names:
        force[n][0] -= pos[n][0] * 0.015; force[n][1] -= pos[n][1] * 0.015
        pos[n][0] += max(-0.05, min(0.05, force[n][0]))
        pos[n][1] += max(-0.05, min(0.05, force[n][1]))

xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
sx = lambda x: MARGIN + (x - min(xs)) / (max(xs) - min(xs)) * (W - 2 * MARGIN)
sy = lambda y: MARGIN + (y - min(ys)) / (max(ys) - min(ys)) * (H - 2 * MARGIN)
degree = {n: 0 for n in nodes}
for a, b in edges:
    degree[a] += 1; degree[b] += 1

out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">']
for a, b in sorted(edges):
    out.append(f'<line x1="{sx(pos[a][0]):.1f}" y1="{sy(pos[a][1]):.1f}" '
               f'x2="{sx(pos[b][0]):.1f}" y2="{sy(pos[b][1]):.1f}" stroke="#3a4250" stroke-width="1.3"/>')
for n, kind in sorted(nodes.items()):
    x, y, r = sx(pos[n][0]), sy(pos[n][1]), 4.5 + degree[n] * 0.85
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 6:.1f}" fill="{COLORS[kind]}" opacity="0.12"/>')
    out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{COLORS[kind]}"/>')
out.append("</svg>")
print("\n".join(out))
