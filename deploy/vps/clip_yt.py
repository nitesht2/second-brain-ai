#!/usr/bin/env python3
"""YouTube caption fetch (no download, dodges datacenter bot-wall).
Usage: clip_yt.py <youtube_url>. Writes transcript md to raw/."""
import re, sys
from pathlib import Path
from datetime import datetime
VAULT = Path.home() / 'SecondBrain'; RAW = VAULT / 'raw'

def vid(u):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})', u)
    return m.group(1) if m else None
def safe(s, n=80):
    s = re.sub(r'[^\w\s-]', '', s or '').strip(); return (re.sub(r'[\s_-]+',' ',s)[:n] or 'clip').strip()

def main():
    url = sys.argv[1]; v = vid(url)
    if not v: print('not a youtube url'); return 1
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        rows = YouTubeTranscriptApi().fetch(v)
        text = ' '.join(r.text for r in rows).strip()
    except Exception as e:
        print(f'caption fetch failed: {e}'); return 2
    if not text: print('empty'); return 1
    RAW.mkdir(parents=True, exist_ok=True)
    stem = safe('YouTube ' + v)
    fp = RAW / f'{stem}.md'
    fp.write_text(f'''---
title: "YouTube {v}"
source: {url}
platform: YouTube
created: {datetime.now().strftime('%Y-%m-%d')}
tags: [youtube, video, transcript]
---

# YouTube {v}

Source: {url}

## Transcript

{text}
''', encoding='utf-8')
    print(f'wrote {fp} ({len(text)} chars) -> watcher ingests'); return 0
if __name__ == '__main__': sys.exit(main())
