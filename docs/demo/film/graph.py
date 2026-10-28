"""Lay out the demo vault graph for the hero film and write graph.json.

Usage: python3 docs/demo/film/graph.py

The film ingests examples/demo-vault/raw/evergreen-notes.md, so the three
notes that ingest would plausibly create are added as `new` nodes. Positions
are in film world pixels, centred on the 1920x1080 stage.
"""
import json
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIKI = HERE.parents[2] / "examples" / "demo-vault" / "wiki"
KINDS = ("sources", "entities", "concepts", "synthesis")
NEW = {
    "Matuschak on Evergreen Notes": ("sources", ["Evergreen Notes", "Andy Matuschak"]),
    "Evergreen Notes": ("concepts", ["Zettelkasten", "Atomic Notes", "Feynman Technique", "Active Recall"]),
    "Andy Matuschak": ("entities", ["Evergreen Notes"]),
}
W, H, CX, CY = 3000, 1700, 960, 540

nodes = {p.stem: p.parent.name for p in WIKI.rglob("*.md") if p.parent.name in KINDS}
edges = set()
for p in WIKI.rglob("*.md"):
    if p.stem in nodes:
        for link in re.findall(r"\[\[([^\]]+)\]\]", p.read_text(encoding="utf-8")):
            if link in nodes and link != p.stem:
                edges.add(tuple(sorted((p.stem, link))))
new_edges = set()
for name, (kind, links) in NEW.items():
    nodes[name] = kind
    new_edges.update(tuple(sorted((name, l))) for l in links)
all_edges = edges | new_edges

random.seed(5)
pos = {n: [random.uniform(-1, 1), random.uniform(-1, 1)] for n in nodes}
names = sorted(nodes)
for _ in range(900):
    force = {n: [0.0, 0.0] for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            k = 0.02 / (dx * dx + dy * dy + 1e-4)
            force[a][0] += dx * k; force[a][1] += dy * k
            force[b][0] -= dx * k; force[b][1] -= dy * k
    for a, b in all_edges:
        dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
        d = math.hypot(dx, dy) + 1e-6
        k = (d - 0.3) * 0.05
        force[a][0] += dx / d * k; force[a][1] += dy / d * k
        force[b][0] -= dx / d * k; force[b][1] -= dy / d * k
    for n in names:
        force[n][0] -= pos[n][0] * 0.015; force[n][1] -= pos[n][1] * 0.015
        pos[n][0] += max(-0.05, min(0.05, force[n][0]))
        pos[n][1] += max(-0.05, min(0.05, force[n][1]))

# widescreen: stretch x, then fit into W x H around the stage centre
xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
sx = lambda x: CX - W / 2 + (x - min(xs)) / (max(xs) - min(xs)) * W
sy = lambda y: CY - H / 2 + (y - min(ys)) / (max(ys) - min(ys)) * H
degree = {n: 0 for n in nodes}
for a, b in all_edges:
    degree[a] += 1; degree[b] += 1

out = {
    "nodes": [{"id": n, "kind": k, "x": round(sx(pos[n][0]), 1), "y": round(sy(pos[n][1]), 1),
               "deg": degree[n], "new": n in NEW} for n, k in sorted(nodes.items())],
    "edges": [{"a": a, "b": b, "new": (a, b) in new_edges} for a, b in sorted(all_edges)],
}
(HERE / "graph.json").write_text(json.dumps(out, indent=1))
print(len(out["nodes"]), "nodes", len(out["edges"]), "edges")
