#!/usr/bin/env python3
"""Build/refresh the semantic-search index over the SecondBrain wiki.
Embeds each note (title + body) with fastembed (bge-small, CPU, local, no API).
Stores ~/SecondBrain/.semantic/{embeddings.npy, meta.json}. Incremental by mtime."""
import json, re
from pathlib import Path
import numpy as np
VAULT=Path.home()/"SecondBrain"; WIKI=VAULT/"wiki"; OUT=VAULT/".semantic"
MODEL="BAAI/bge-small-en-v1.5"; MAXCHARS=4000
def notes():
    for f in WIKI.rglob("*.md"):
        if any(p.startswith('.') for p in f.parts): continue
        if f.name in ("index.md","log.md","SCHEMA.md"): continue
        yield f
def load_prev():
    try:
        meta=json.loads((OUT/"meta.json").read_text()); emb=np.load(OUT/"embeddings.npy")
        return {m["path"]:(i,m) for i,m in enumerate(meta)}, emb
    except Exception: return {}, None
def main():
    OUT.mkdir(exist_ok=True)
    prev, prev_emb = load_prev()
    rows=[]; to_embed=[]; reuse=[]
    for f in notes():
        p=str(f); mt=f.stat().st_mtime
        if p in prev and abs(prev[p][1].get("mtime",0)-mt)<1:
            reuse.append((len(rows), prev[p][0])); rows.append(prev[p][1])
        else:
            txt=f.read_text(encoding="utf-8",errors="ignore")
            body=re.sub(r'^---.*?---','',txt,flags=re.S).strip()
            rows.append({"name":f.stem,"path":p,"mtime":mt,"snippet":' '.join(body.split())[:200]})
            to_embed.append((len(rows)-1, f.stem+"\n"+body[:MAXCHARS]))
    dim=prev_emb.shape[1] if prev_emb is not None else 384
    emb=np.zeros((len(rows),dim),dtype=np.float32)
    for fi,pi in reuse: emb[fi]=prev_emb[pi]
    if to_embed:
        from fastembed import TextEmbedding
        model=TextEmbedding(MODEL)
        for (fi,_),v in zip(to_embed, model.embed([t for _,t in to_embed])):
            v=np.asarray(v,dtype=np.float32); emb[fi]=v/(np.linalg.norm(v)+1e-9)
    np.save(OUT/"embeddings.npy", emb); (OUT/"meta.json").write_text(json.dumps(rows))
    print(f"indexed {len(rows)} notes ({len(to_embed)} new, {len(reuse)} reused) dim={dim}")
if __name__=="__main__": main()
