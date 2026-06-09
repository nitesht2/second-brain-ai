#!/usr/bin/env python3
"""Query the semantic index. Usage: semantic_query.py "<query>" [k]. Prints JSON top-k."""
import json, sys
from pathlib import Path
import numpy as np
OUT=Path.home()/"SecondBrain"/".semantic"; MODEL="BAAI/bge-small-en-v1.5"
def main():
    q=sys.argv[1] if len(sys.argv)>1 else ""
    k=int(sys.argv[2]) if len(sys.argv)>2 else 8
    if not q.strip(): print("[]"); return
    meta=json.loads((OUT/"meta.json").read_text()); emb=np.load(OUT/"embeddings.npy")
    from fastembed import TextEmbedding
    qv=np.asarray(list(TextEmbedding(MODEL).embed([q]))[0],dtype=np.float32)
    qv=qv/(np.linalg.norm(qv)+1e-9)
    sims=emb@qv; idx=np.argsort(-sims)[:k]
    print(json.dumps([{"name":meta[i]["name"],"score":round(float(sims[i]),3),"snippet":meta[i].get("snippet","")} for i in idx]))
if __name__=="__main__": main()
