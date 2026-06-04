#!/usr/bin/env python3
"""book2chapters.py — convert a book (PDF/ePub/docx) to Markdown, split into
chapters, and STAGE them under books/<slug>/ for the idle-aware drip feeder
(book_drip.sh) to ingest one at a time. Does NOT touch raw/ directly.

Usage: book2chapters.py <file-or-url> [--title "Book Title"] [--max-words N]
"""
import sys, os, re, argparse, tempfile, urllib.request

VAULT = '/root/SecondBrain'
BOOKS = os.path.join(VAULT, 'books')
DEFAULT_MAX_WORDS = 3500   # fallback chunk size (fits ingest context comfortably)

def slug(s):
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    return re.sub(r'[\s_-]+', '-', s)[:60] or 'book'

def split_by_heading(md):
    # find the shallowest heading level that yields a sane chapter count
    for lvl in (1, 2, 3):
        pat = re.compile(r'^#{%d}\s+\S' % lvl, re.M)
        idxs = [m.start() for m in pat.finditer(md)]
        if 3 <= len(idxs) <= 60:
            parts = []
            for i, start in enumerate(idxs):
                end = idxs[i+1] if i+1 < len(idxs) else len(md)
                parts.append(md[start:end].strip())
            return parts
    return None

def split_by_size(md, max_words):
    paras = re.split(r'\n\s*\n', md)
    chunks, cur, n = [], [], 0
    for p in paras:
        w = len(p.split())
        if n + w > max_words and cur:
            chunks.append('\n\n'.join(cur)); cur, n = [], 0
        cur.append(p); n += w
    if cur: chunks.append('\n\n'.join(cur))
    return chunks

def title_of(chunk, fallback):
    m = re.match(r'^#{1,3}\s+(.+)', chunk)
    return (m.group(1).strip() if m else fallback)[:60]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('--title', default=None)
    ap.add_argument('--max-words', type=int, default=DEFAULT_MAX_WORDS)
    a = ap.parse_args()

    from markitdown import MarkItDown
    md_engine = MarkItDown()
    tmp = None
    try:
        if a.src.startswith(('http://','https://')):
            ext = os.path.splitext(a.src.split('?')[0])[1] or '.pdf'
            fd, tmp = tempfile.mkstemp(suffix=ext); os.close(fd)
            req = urllib.request.Request(a.src, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp,'wb') as f: f.write(r.read())
            text = md_engine.convert(tmp).text_content
            book_title = a.title or os.path.basename(a.src.split('?')[0])
        else:
            if not os.path.exists(a.src): print('file not found:', a.src); sys.exit(1)
            text = md_engine.convert(a.src).text_content
            book_title = a.title or os.path.splitext(os.path.basename(a.src))[0]
    finally:
        if tmp and os.path.exists(tmp): os.remove(tmp)

    text = (text or '').strip()
    if not text: print('conversion produced no text'); sys.exit(1)

    parts = split_by_heading(text)
    how = 'heading'
    if not parts:
        parts = split_by_size(text, a.max_words); how = 'size'

    bslug = slug(book_title)
    outdir = os.path.join(BOOKS, bslug)
    os.makedirs(outdir, exist_ok=True)
    total = len(parts)
    for i, chunk in enumerate(parts, 1):
        ch_title = title_of(chunk, f'Part {i}')
        header = f'<!-- book: {book_title} | chapter {i}/{total}: {ch_title} | split: {how} -->\n\n'
        fn = f'{i:02d}-{slug(ch_title)}.md'
        with open(os.path.join(outdir, fn), 'w') as f:
            f.write(header + chunk + '\n')
    print(f'OK: "{book_title}" -> {total} chapters staged in books/{bslug}/ (split by {how}).')
    print(f'The drip feeder will ingest them one at a time while the brain is idle.')

if __name__ == '__main__':
    main()
