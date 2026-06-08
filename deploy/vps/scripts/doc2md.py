#!/usr/bin/env python3
"""doc2md.py - convert a document (PDF/DOCX/PPTX/XLSX/image/HTML/CSV/ePub) or URL
to Markdown for ingest. SIZE-AWARE:
  - small (<= MAX_WORDS) -> one file in raw/  (single rich note)
  - large (>  MAX_WORDS) -> chunks staged under _staging/<slug>/ for book_drip.sh

Article URLs: trafilatura (clean extraction, strips nav/ads) first; if the page is
JS-rendered/thin, fall back to a LightPanda headless render -> trafilatura; if that
still yields nothing (e.g. a PDF/doc URL), fall back to markitdown download+convert.

Usage: doc2md.py <file-or-url> [--title "Name"] [--max-words N] [--dry-run]
"""
import sys, os, re, argparse, tempfile, urllib.request, subprocess, time, socket

VAULT='/root/SecondBrain'; RAW=VAULT+'/raw'; STAGING=VAULT+'/_staging'
LIGHTPANDA='/root/.local/bin/lightpanda'
MAX_WORDS=5000
CHUNK_WORDS=3500
MIN_ARTICLE_CHARS=300   # trafilatura result shorter than this = "thin" -> try render

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

def _port_ready(port, timeout=8):
    end=time.time()+timeout
    while time.time()<end:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1',port))==0: return True
        time.sleep(0.3)
    return False

def _render_html(url, port=9222):
    """Render a JS page with LightPanda over CDP; return HTML or None. Lazy: only
    spawned when trafilatura's plain fetch came back thin."""
    if not os.path.exists(LIGHTPANDA): return None
    proc=subprocess.Popen([LIGHTPANDA,'serve','--host','127.0.0.1','--port',str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not _port_ready(port): return None
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b=p.chromium.connect_over_cdp('http://127.0.0.1:%d'%port)
            pg=b.new_page(); pg.goto(url, timeout=30000, wait_until='load')
            html=pg.content(); b.close(); return html
    except Exception as e:
        sys.stderr.write('lightpanda render failed: %r\n'%e); return None
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception: proc.kill()

def extract_article(url):
    """(clean_text, title, how) for an article URL, or (None,None,None) if not an article."""
    import trafilatura
    html=trafilatura.fetch_url(url)
    opts=dict(include_comments=False, include_links=False, favor_recall=True)
    txt=trafilatura.extract(html, **opts) if html else None
    how='trafilatura'
    if not txt or len(txt)<MIN_ARTICLE_CHARS:
        rhtml=_render_html(url)
        if rhtml:
            t2=trafilatura.extract(rhtml, **opts)
            if t2 and len(t2)>=MIN_ARTICLE_CHARS: txt,how=t2,'lightpanda+trafilatura'
    if not txt or len(txt)<MIN_ARTICLE_CHARS:
        return None,None,None
    title=None
    try:
        md=trafilatura.extract_metadata(html) if html else None
        title=getattr(md,'title',None)
    except Exception: pass
    return txt.strip(), title, how

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('--title',default=None)
    ap.add_argument('--max-words',type=int,default=MAX_WORDS); ap.add_argument('--dry-run',action='store_true')
    a=ap.parse_args()
    from markitdown import MarkItDown
    eng=MarkItDown(); tmp=None; text=None; name=None; how='markitdown'
    try:
        if a.src.startswith(('http://','https://')):
            text,atitle,how = extract_article(a.src)
            if text:
                name=a.title or atitle or os.path.basename(a.src.split('?')[0]) or 'web-article'
            else:
                ext=os.path.splitext(a.src.split('?')[0])[1] or '.bin'
                fd,tmp=tempfile.mkstemp(suffix=ext); os.close(fd)
                rq=urllib.request.Request(a.src,headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(rq,timeout=120) as r, open(tmp,'wb') as f: f.write(r.read())
                text=eng.convert(tmp).text_content; how='markitdown'
                name=a.title or os.path.basename(a.src.split('?')[0]) or 'web-doc'
        else:
            if not os.path.exists(a.src): print('file not found:',a.src); sys.exit(1)
            text=eng.convert(a.src).text_content; name=a.title or os.path.splitext(os.path.basename(a.src))[0]
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)
    text=(text or '').strip()
    if not text: print('conversion produced no text'); sys.exit(1)
    words=len(text.split())

    if a.dry_run:
        print(f'[dry-run] via={how} words={words} title={name!r}')
        print('--- first 500 chars ---'); print(text[:500]); return

    if words<=a.max_words:
        os.makedirs(RAW,exist_ok=True)
        out=os.path.join(RAW, slug(name)+'.md')
        open(out,'w').write(f'<!-- source: {a.src} | doc2md ({how}) -->\n\n'+text+'\n')
        print(f'OK small doc ({words} words, {how}) -> {out}. Watcher will ingest it.')
    else:
        parts=split_by_heading(text); hw='heading'
        if not parts: parts=split_by_size(text); hw='size'
        sl=slug(name); d=os.path.join(STAGING,sl); os.makedirs(d,exist_ok=True); tot=len(parts)
        for i,c in enumerate(parts,1):
            ct=title_of(c,f'Part {i}')
            open(os.path.join(d,f'{i:02d}-{slug(ct)}.md'),'w').write(
                f'<!-- source: {name} | chunk {i}/{tot}: {ct} | split: {hw} | {how} -->\n\n'+c+'\n')
        print(f'OK large doc ({words} words, {how}) -> {tot} chunks staged in _staging/{sl}/ (by {hw}).')

if __name__=='__main__': main()
