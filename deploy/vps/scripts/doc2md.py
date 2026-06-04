#!/usr/bin/env python3
"""doc2md.py — convert a document (PDF/DOCX/PPTX/XLSX/image/HTML/CSV) to Markdown
and drop it into raw/ so the watcher ingests it through the normal pipeline.

Usage:  doc2md.py <file-path-or-url>
Mirrors clip.py (video path): convert -> raw/ -> auto-ingest.
"""
import sys, os, re, tempfile, urllib.request, datetime

RAW = "/root/SecondBrain/raw"

def slug(s):
    s = re.sub(r'[^\w\s-]', '', s).strip()
    return re.sub(r'[\s_-]+', '-', s)[:80] or 'document'

def main():
    if len(sys.argv) < 2:
        print('usage: doc2md.py <file-or-url>'); sys.exit(1)
    src = sys.argv[1]
    from markitdown import MarkItDown
    md = MarkItDown()
    tmp = None
    try:
        if src.startswith(('http://', 'https://')):
            # docs are not IP-blocked like YouTube; plain fetch is fine
            ext = os.path.splitext(src.split('?')[0])[1] or '.bin'
            fd, tmp = tempfile.mkstemp(suffix=ext); os.close(fd)
            req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                f.write(r.read())
            result = md.convert(tmp)
            name = slug(os.path.basename(src.split('?')[0]) or 'web-document')
        else:
            if not os.path.exists(src):
                print(f'file not found: {src}'); sys.exit(1)
            result = md.convert(src)
            name = slug(os.path.splitext(os.path.basename(src))[0])
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)

    body = (result.text_content or '').strip()
    if not body:
        print('conversion produced no text'); sys.exit(1)
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    out = os.path.join(RAW, f'{name}.md')
    header = f'<!-- source: {src} | converted: {today} via markitdown -->\n\n'
    with open(out, 'w') as f:
        f.write(header + body + '\n')
    print(f'OK -> {out} ({len(body)} chars). Watcher will ingest it.')

if __name__ == '__main__':
    main()
