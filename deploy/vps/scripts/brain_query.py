#!/usr/bin/env python3
"""brain_query.py - semantic search over the SecondBrain wiki from the terminal.

Reuses the index built by semantic_index.py (~/SecondBrain/.semantic/), so it is
the read side of the same embeddings the Discord bot uses: fastembed bge-small,
CPU, local, no API. Embeddings are stored unit-normalized, so cosine similarity
is a plain dot product.

Usage:
    brain_query.py "how do I sell AI agents to local businesses"
    brain_query.py "self-improving agent loop" -k 10
    brain_query.py "cost optimization" --type concepts          # entities|concepts|sources|synthesis|decisions|projects|episodic
    brain_query.py "hermes profiles" --full                     # show snippets
    brain_query.py "agent loop" --paths                         # paths only (pipe-friendly)

Env: SB_VAULT overrides the vault root (default ~/SecondBrain).
Build/refresh the index first with: semantic_index.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

VAULT = Path(os.environ.get("SB_VAULT", str(Path.home() / "SecondBrain"))).expanduser()
OUT = VAULT / ".semantic"
MODEL = "BAAI/bge-small-en-v1.5"  # must match semantic_index.py


def load_index() -> tuple[np.ndarray, list[dict]]:
    emb_path, meta_path = OUT / "embeddings.npy", OUT / "meta.json"
    if not emb_path.exists() or not meta_path.exists():
        sys.exit(f"no index at {OUT} — build it first with semantic_index.py")
    info_path = OUT / "index_info.json"
    if info_path.exists():  # absent on indexes built before fingerprinting, then trust as before
        built_with = json.loads(info_path.read_text()).get("model")
        if built_with != MODEL:
            sys.exit(f"index built with {built_with}, script expects {MODEL}; re-run semantic_index.py")
    emb = np.load(emb_path)
    meta = json.loads(meta_path.read_text())
    if len(meta) != emb.shape[0]:
        sys.exit(f"index out of sync ({len(meta)} meta rows vs {emb.shape[0]} vectors); re-run semantic_index.py")
    return emb, meta


def note_type(path: str) -> str:
    """The wiki subfolder a note lives in (entities/concepts/sources/...)."""
    parts = Path(path).parts
    if "wiki" in parts:
        idx = parts.index("wiki")
        if idx + 1 < len(parts) - 1:  # a subfolder exists between wiki/ and the filename
            return parts[idx + 1]
    return ""


def embed_query(text: str) -> np.ndarray:
    from fastembed import TextEmbedding
    vec = np.asarray(next(iter(TextEmbedding(MODEL).embed([text]))), dtype=np.float32)
    return vec / (np.linalg.norm(vec) + 1e-9)


def search(query: str, top_k: int, type_filter: str | None) -> list[tuple[float, dict]]:
    emb, meta = load_index()
    sims = emb @ embed_query(query)  # stored vectors are unit-normalized
    order = sims.argsort()[::-1]
    hits: list[tuple[float, dict]] = []
    for i in order:
        row = meta[i]
        if type_filter and f"/wiki/{type_filter}/" not in row.get("path", ""):
            continue
        hits.append((float(sims[i]), row))
        if len(hits) >= top_k:
            break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="Semantic search over the SecondBrain wiki.")
    ap.add_argument("query", nargs="+", help="natural-language question")
    ap.add_argument("-k", "--top", type=int, default=8, help="number of results (default 8)")
    ap.add_argument("--type", default=None,
                    help="restrict to a wiki subfolder: entities|concepts|sources|synthesis|decisions|projects|episodic")
    ap.add_argument("--full", action="store_true", help="show each note's snippet")
    ap.add_argument("--paths", action="store_true", help="print matching file paths only (pipe-friendly)")
    args = ap.parse_args()

    query = " ".join(args.query)
    hits = search(query, args.top, args.type)
    if not hits:
        print("no matches" + (f" in {args.type}" if args.type else ""))
        return 0

    if args.paths:
        for _, row in hits:
            print(row.get("path", ""))
        return 0

    print(f'\nQ: {query}\n')
    for score, row in hits:
        typ = note_type(row.get("path", ""))
        print(f"  {score:.3f}  [{typ}] {row.get('name', '?')}")
        if args.full and row.get("snippet"):
            print(f"         {row['snippet'][:200]}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
