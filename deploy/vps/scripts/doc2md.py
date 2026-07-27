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
import sys, os, re, argparse, tempfile, urllib.request, urllib.parse, urllib.error, subprocess, time, socket, hashlib, shutil, ipaddress, http.client

VAULT='/root/SecondBrain'; RAW=VAULT+'/raw'; STAGING=VAULT+'/_staging'
LIGHTPANDA='/root/.local/bin/lightpanda'
MAX_WORDS=5000
CHUNK_WORDS=3500
MIN_ARTICLE_CHARS=300   # trafilatura result shorter than this = "thin" -> try render

# ── SSRF guard ──────────────────────────────────────────────────────────────
# Bookmarked URLs are attacker-influenceable and redirects used to be followed
# blind, so a public URL could 302 to 127.0.0.1 or metadata space. Every hop of
# every fetch must be http(s) and resolve only to global addresses (same policy
# as harvest_x.py is_safe_public_url). Connects pin the vetted IP so a DNS
# rebind between resolve and connect cannot swap in an internal host. Fails closed.
MAX_REDIRECTS=5
FETCH_TIMEOUT=120

def _public_ip(url):
    """Vet url; return one resolved global IP to pin. Raises URLError otherwise."""
    p=urllib.parse.urlparse(url)
    if p.scheme not in ('http','https'): raise urllib.error.URLError('blocked scheme %r'%p.scheme)
    if not p.hostname: raise urllib.error.URLError('no host in url')
    try: port=p.port   # raises ValueError on a malformed port
    except ValueError: raise urllib.error.URLError('bad port in url')
    try: infos=socket.getaddrinfo(p.hostname, port or (443 if p.scheme=='https' else 80), proto=socket.IPPROTO_TCP)
    except OSError as e: raise urllib.error.URLError('resolve failed %s: %s'%(p.hostname,e))
    if not infos: raise urllib.error.URLError('no addresses for %s'%p.hostname)
    for i in infos:
        try: ip=ipaddress.ip_address(i[4][0])
        except ValueError: raise urllib.error.URLError('bad address %r for %s'%(i[4][0],p.hostname))
        if not ip.is_global: raise urllib.error.URLError('non-public address %s for %s'%(ip,p.hostname))
    return infos[0][4][0]

class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self,host,pin=None,**kw): super().__init__(host,**kw); self._pin=pin
    def connect(self): self.sock=socket.create_connection((self._pin,self.port),self.timeout)

class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,pin=None,**kw): super().__init__(host,**kw); self._pin=pin
    def connect(self):
        self.sock=socket.create_connection((self._pin,self.port),self.timeout)
        if self._tunnel_host: self._tunnel()
        self.sock=self._context.wrap_socket(self.sock, server_hostname=self.host)

class _GuardHTTP(urllib.request.HTTPHandler):
    def http_open(self,req):
        pin=_public_ip(req.full_url)
        return self.do_open(lambda h,**kw:_PinnedHTTP(h,pin=pin,**kw), req)

class _GuardHTTPS(urllib.request.HTTPSHandler):
    def https_open(self,req):
        pin=_public_ip(req.full_url)
        return self.do_open(lambda h,**kw:_PinnedHTTPS(h,pin=pin,**kw), req, context=self._context)

class _GuardRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections=MAX_REDIRECTS
    def redirect_request(self,req,fp,code,msg,hdrs,newurl):
        _public_ip(newurl)  # vet every hop before following it
        return super().redirect_request(req,fp,code,msg,hdrs,newurl)

_OPENER=urllib.request.build_opener(_GuardHTTP,_GuardHTTPS,_GuardRedirect)

def _guarded_get(url, timeout=FETCH_TIMEOUT):
    """GET via the guarded opener; returns (body bytes, declared charset or None)."""
    rq=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with _OPENER.open(rq, timeout=timeout) as r:
        return r.read(), r.headers.get_content_charset()

def slug(s):
    s=re.sub(r'[^\w\s-]','',s).strip().lower(); return re.sub(r'[\s_-]+','-',s)[:60] or 'doc'

def split_by_heading(md):
    for lvl in (1,2,3):
        idxs=[m.start() for m in re.finditer(r'^#{%d}\s+\S'%lvl, md, re.M)]
        if 3<=len(idxs)<=60:
            parts=[md[idxs[i]:(idxs[i+1] if i+1<len(idxs) else len(md))].strip() for i in range(len(idxs))]
            pre=md[:idxs[0]].strip()   # keep intro/abstract before the first heading
            if pre: parts.insert(0,pre)
            return parts
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

def _port_ready(proc, port, timeout=8):
    end=time.time()+timeout
    while time.time()<end:
        if proc.poll() is not None: return False   # lightpanda died, stop waiting
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1',port))==0: return True
        time.sleep(0.3)
    return False

def _render_html(url):
    """Render a JS page with LightPanda over CDP; return HTML or None. Lazy: only
    spawned when trafilatura's plain fetch came back thin."""
    try: _public_ip(url)
    except Exception as e:
        sys.stderr.write('refusing render of unsafe url: %r\n'%e); return None
    if not os.path.exists(LIGHTPANDA): return None
    with socket.socket() as s: s.bind(('127.0.0.1',0)); port=s.getsockname()[1]   # ephemeral port, no clash between runs
    proc=subprocess.Popen([LIGHTPANDA,'serve','--host','127.0.0.1','--port',str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not _port_ready(proc, port): return None
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b=p.chromium.connect_over_cdp('http://127.0.0.1:%d'%port)
            pg=b.new_page()
            # goto() follows 30x itself and loads subresources, so vetting `url`
            # above is not enough: vet every request the browser makes. Fails
            # closed, since a raise here lands in the except and returns None.
            def _vet(route, request):
                try: _public_ip(request.url)
                except Exception: route.abort(); return
                route.continue_()
            pg.route('**/*', _vet)
            pg.goto(url, timeout=30000, wait_until='load')
            _public_ip(pg.url)   # backstop if interception silently no-ops
            html=pg.content(); b.close(); return html
    except Exception as e:
        sys.stderr.write('lightpanda render failed: %r\n'%e); return None
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except Exception:
            proc.kill(); proc.wait()   # reap, no zombie

def extract_article(url):
    """(clean_text, title, how) for an article URL, or (None,None,None) if not an article."""
    import trafilatura
    try:
        raw,cs=_guarded_get(url); html=raw.decode(cs or 'utf-8','replace')
    except Exception as e:
        sys.stderr.write('guarded fetch failed: %r\n'%e); html=None
    opts=dict(include_comments=False, include_links=False, favor_recall=True)
    txt=trafilatura.extract(html, **opts) if html else None
    how='trafilatura'; used=html   # html the winning extraction came from
    if not txt or len(txt)<MIN_ARTICLE_CHARS:
        rhtml=_render_html(url)
        if rhtml:
            t2=trafilatura.extract(rhtml, **opts)
            if t2 and len(t2)>=MIN_ARTICLE_CHARS: txt,how,used=t2,'lightpanda+trafilatura',rhtml
    if not txt or len(txt)<MIN_ARTICLE_CHARS:
        return None,None,None
    title=None
    try:
        md=trafilatura.extract_metadata(used) if used else None
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
                try:
                    with _OPENER.open(rq,timeout=FETCH_TIMEOUT) as r, open(tmp,'wb') as f: f.write(r.read())
                except (urllib.error.URLError, OSError) as e:
                    print('download refused/failed:',e); sys.exit(1)
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
        if os.path.exists(out):   # same slug, different doc: suffix with source hash instead of clobbering
            out=os.path.join(RAW, slug(name)+'-'+hashlib.sha256(a.src.encode()).hexdigest()[:8]+'.md')
        open(out,'w').write(f'<!-- source: {a.src} | doc2md ({how}) -->\n\n'+text+'\n')
        print(f'OK small doc ({words} words, {how}) -> {out}. Watcher will ingest it.')
    else:
        parts=split_by_heading(text); hw='heading'
        if not parts: parts=split_by_size(text); hw='size'
        sl=slug(name); d=os.path.join(STAGING,sl)
        shutil.rmtree(d, ignore_errors=True)   # clear leftovers from a prior same-slug ingest
        os.makedirs(d,exist_ok=True); tot=len(parts)
        for i,c in enumerate(parts,1):
            ct=title_of(c,f'Part {i}')
            open(os.path.join(d,f'{i:02d}-{slug(ct)}.md'),'w').write(
                f'<!-- source: {name} | chunk {i}/{tot}: {ct} | split: {hw} | {how} -->\n\n'+c+'\n')
        print(f'OK large doc ({words} words, {how}) -> {tot} chunks staged in _staging/{sl}/ (by {hw}).')

if __name__=='__main__': main()
