#!/usr/bin/env python3
"""doc2md.py — convert a document (PDF/DOCX/PPTX/XLSX/image/HTML/CSV/ePub) or URL
to Markdown for ingest. SIZE-AWARE:
  - small (<= MAX_WORDS) -> one file in raw/  (single rich note)
  - large (>  MAX_WORDS) -> split into chunks staged under _staging/<slug>/,
                            which book_drip.sh feeds in one at a time when idle.
Works for ANY large file, books are just one case.

Usage: doc2md.py <file-or-url> [--title "Name"] [--max-words N]
"""
import sys, os, re, argparse, tempfile, urllib.request

VAULT='/root/SecondBrain'; RAW=VAULT+'/raw'; STAGING=VAULT+'/_staging'
MAX_WORDS=5000        # above this, one ingest gets lossy -> chunk instead
CHUNK_WORDS=3500      # target size per chunk on size-based split

def slug(s):
    s=re.sub(r'[^\w\s-]','',s).strip().lower(); return re.sub(r'[\s_-]+','-',s)[:60] or 'doc'

def split_by_heading(md):
    for lvl in (1,2,3):
        idxs=[m.start() for m in re.finditer(r'^#{%d}\s+\S'%lvl, md, re.M)]
        if 3<=len(idxs)<=60:
            return [md[idxs[i]:(idxs[i+1] if i+1<len(idxs) else len(md))].strip() for i in range(len(idxs))]
    return None

def split_by_size(md):
    out,cur,n=[],[],0
    for p in re.split(r'\n\s*\n', md):
        w=len(p.split())
        if n+w>CHUNK_WORDS and cur: out.append('\n\n'.join(cur)); cur,n=[],0
        cur.append(p); n+=w
    if cur: out.append('\n\n'.join(cur))
    return out

def title_of(c,fb):
    m=re.match(r'^#{1,3}\s+(.+)', c); return (m.group(1).strip() if m else fb)[:60]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('--title',default=None)
    ap.add_argument('--max-words',type=int,default=MAX_WORDS); a=ap.parse_args()
    from markitdown import MarkItDown
    eng=MarkItDown(); tmp=None
    try:
        if a.src.startswith(('http://','https://')):
            ext=os.path.splitext(a.src.split('?')[0])[1] or '.bin'
            fd,tmp=tempfile.mkstemp(suffix=ext); os.close(fd)
            rq=urllib.request.Request(a.src,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(rq,timeout=120) as r, open(tmp,'wb') as f: f.write(r.read())
            text=eng.convert(tmp).text_content; name=a.title or os.path.basename(a.src.split('?')[0]) or 'web-doc'
        else:
            if not os.path.exists(a.src): print('file not found:',a.src); sys.exit(1)
            text=eng.convert(a.src).text_content; name=a.title or os.path.splitext(os.path.basename(a.src))[0]
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)
    text=(text or '').strip()
    if not text: print('conversion produced no text'); sys.exit(1)

    words=len(text.split())
    if words<=a.max_words:
        os.makedirs(RAW,exist_ok=True)
        out=os.path.join(RAW, slug(name)+'.md')
        open(out,'w').write(f'<!-- source: {a.src} | doc2md -->\n\n'+text+'\n')
        print(f'OK small doc ({words} words) -> {out}. Watcher will ingest it.')
    else:
        parts=split_by_heading(text); how='heading'
        if not parts: parts=split_by_size(text); how='size'
        sl=slug(name); d=os.path.join(STAGING,sl); os.makedirs(d,exist_ok=True); tot=len(parts)
        for i,c in enumerate(parts,1):
            ct=title_of(c,f'Part {i}')
            open(os.path.join(d,f'{i:02d}-{slug(ct)}.md'),'w').write(
                f'<!-- source: {name} | chunk {i}/{tot}: {ct} | split: {how} -->\n\n'+c+'\n')
        print(f'OK large doc ({words} words) -> {tot} chunks staged in _staging/{sl}/ (by {how}). Drip feeder ingests them while idle.')

if __name__=='__main__': main()
