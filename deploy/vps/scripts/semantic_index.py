#!/usr/bin/env python3
"""Build/refresh the semantic-search index over the SecondBrain wiki.
Embeds each note (title + body) with fastembed (bge-small, CPU, local, no API).
Stores ~/SecondBrain/.semantic/{embeddings.npy, meta.json, index_info.json}. Incremental by mtime."""
import json, os, re, sys
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
        info=json.loads((OUT/"index_info.json").read_text())  # model fingerprint; missing sidecar raises and forces full re-embed
        meta=json.loads((OUT/"meta.json").read_text()); emb=np.load(OUT/"embeddings.npy")
        if emb.shape[0]!=len(meta): return {}, None  # desynced pair: force clean rebuild
        if info.get("model")!=MODEL or info.get("dim")!=emb.shape[1]: return {}, None
        return {m["path"]:(i,m) for i,m in enumerate(meta)}, emb
    except Exception: return {}, None
def main():
    OUT.mkdir(exist_ok=True)
    prev, prev_emb = load_prev()
    rows=[]; to_embed=[]; reuse=[]
    for f in notes():
        p=str(f); st=f.stat(); mt=st.st_mtime; sz=st.st_size
        if p in prev and prev[p][1].get("mtime")==mt and prev[p][1].get("size")==sz:
            reuse.append((len(rows), prev[p][0])); rows.append(prev[p][1])
        else:
            txt=f.read_text(encoding="utf-8",errors="ignore")
            body=re.sub(r'^---.*?---','',txt,flags=re.S).strip()
            rows.append({"name":f.stem,"path":p,"mtime":mt,"size":sz,"snippet":' '.join(body.split())[:200]})
            to_embed.append((len(rows)-1, f.stem+"\n"+body[:MAXCHARS]))
    if not rows and (prev or (OUT/"meta.json").exists()): sys.exit(f"wiki empty at {WIKI} but an index exists at {OUT}; refusing to wipe it")  # prev is empty on model mismatch, so check disk too
    dim=prev_emb.shape[1] if prev_emb is not None else 384
    emb=np.zeros((len(rows),dim),dtype=np.float32)
    for fi,pi in reuse: emb[fi]=prev_emb[pi]
    if to_embed:
        from fastembed import TextEmbedding
        model=TextEmbedding(MODEL)
        for (fi,_),v in zip(to_embed, model.embed([t for _,t in to_embed])):
            v=np.asarray(v,dtype=np.float32); emb[fi]=v/(np.linalg.norm(v)+1e-9)
    np.save(OUT/"embeddings.tmp.npy", emb); os.replace(OUT/"embeddings.tmp.npy", OUT/"embeddings.npy")
    (OUT/"meta.tmp.json").write_text(json.dumps(rows)); os.replace(OUT/"meta.tmp.json", OUT/"meta.json")
    (OUT/"index_info.tmp.json").write_text(json.dumps({"model":MODEL,"dim":dim})); os.replace(OUT/"index_info.tmp.json", OUT/"index_info.json")
    print(f"indexed {len(rows)} notes ({len(to_embed)} new, {len(reuse)} reused) dim={dim}")
if __name__=="__main__": main()
